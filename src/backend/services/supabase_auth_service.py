# -------------------------
# SUPABASE AUTH SERVICE
# -------------------------
"""
Minimal Supabase authentication wrapper for AutoReturn.

This service is intentionally scoped to email/password auth only so the
existing Google login flow can remain unchanged.
"""

# -------------------------
# IMPORTS
# -------------------------
import os
from datetime import datetime, timezone
from typing import Dict, Any, List

from dotenv import load_dotenv


class SupabaseAuthService:
    """Small wrapper around Supabase email/password authentication."""

    # -------------------------
    # INIT
    # Loads environment configuration and prepares the lazy client handle.
    # -------------------------
    def __init__(self):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        load_dotenv(os.path.join(project_root, ".env"))

        self.url = (os.getenv("SUPABASE_URL") or "").strip()
        self.anon_key = (os.getenv("SUPABASE_ANON_KEY") or "").strip()
        self._client = None

    # -------------------------
    # IS CONFIGURED
    # Returns whether the required Supabase environment variables exist.
    # -------------------------
    def is_configured(self) -> bool:
        return bool(self.url and self.anon_key)

    # -------------------------
    # GET CLIENT
    # Lazily imports and creates the Supabase client only when needed.
    # -------------------------
    def _get_client(self):
        if self._client is not None:
            return self._client

        if not self.is_configured():
            raise RuntimeError(
                "Supabase is not configured. Set SUPABASE_URL and SUPABASE_ANON_KEY in AutoReturn/.env."
            )

        try:
            from supabase import create_client
        except Exception as exc:
            raise RuntimeError(
                "Supabase client is not installed. Install project requirements and restart the app."
            ) from exc

        self._client = create_client(self.url, self.anon_key)
        return self._client

    # -------------------------
    # SIGN UP
    # Creates a new Supabase auth user with optional full name metadata.
    # -------------------------
    def sign_up(self, email: str, password: str, full_name: str = "") -> Dict[str, Any]:
        client = self._get_client()
        payload: Dict[str, Any] = {
            "email": email,
            "password": password,
        }
        if full_name.strip():
            payload["options"] = {
                "data": {
                    "full_name": full_name.strip()
                }
            }

        response = client.auth.sign_up(payload)
        return self._normalize_auth_response(response)

    # -------------------------
    # SIGN IN
    # Authenticates an existing Supabase user via email/password.
    # -------------------------
    def sign_in(self, email: str, password: str) -> Dict[str, Any]:
        client = self._get_client()
        response = client.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })
        return self._normalize_auth_response(response)

    # -------------------------
    # SET SESSION TOKENS
    # Applies an authenticated session to this client instance.
    # -------------------------
    def set_session_tokens(self, access_token: str, refresh_token: str) -> None:
        if not access_token or not refresh_token:
            return
        client = self._get_client()
        try:
            client.auth.set_session(access_token, refresh_token)
        except Exception as exc:
            raise RuntimeError(f"Could not restore Supabase session: {exc}") from exc

    # -------------------------
    # SIGN OUT
    # Clears the authenticated Supabase session for this client instance.
    # -------------------------
    def sign_out(self) -> None:
        if not self.is_configured():
            return
        client = self._get_client()
        try:
            client.auth.sign_out()
        except Exception as exc:
            raise RuntimeError(f"Could not sign out of Supabase: {exc}") from exc

    # -------------------------
    # GET CONNECTED ACCOUNTS
    # Loads integration ownership rows for the authenticated user.
    # -------------------------
    def get_connected_accounts(self, user_id: str) -> List[Dict[str, Any]]:
        if not user_id:
            return []
        client = self._get_client()
        response = (
            client.table("connected_accounts")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )
        return list(getattr(response, "data", None) or [])

    # -------------------------
    # UPSERT CONNECTED ACCOUNT
    # Creates or updates one provider mapping row for a user.
    # -------------------------
    def upsert_connected_account(
        self,
        user_id: str,
        provider: str,
        provider_account_id: str = "",
        provider_account_email: str = "",
        provider_display_name: str = "",
        connected: bool = True,
    ) -> None:
        if not user_id or not provider:
            return

        client = self._get_client()
        payload = {
            "user_id": user_id,
            "provider": provider,
            "provider_account_id": provider_account_id or None,
            "provider_account_email": provider_account_email or None,
            "provider_display_name": provider_display_name or None,
            "connected": connected,
            "updated_at": self._utc_now_iso(),
            "last_used_at": self._utc_now_iso() if connected else None,
        }
        if connected:
            payload["connected_at"] = self._utc_now_iso()

        client.table("connected_accounts").upsert(
            payload,
            on_conflict="user_id,provider"
        ).execute()

    # -------------------------
    # DISCONNECT CONNECTED ACCOUNT
    # Marks one provider mapping as disconnected for a user.
    # -------------------------
    def disconnect_connected_account(self, user_id: str, provider: str) -> None:
        if not user_id or not provider:
            return

        client = self._get_client()
        client.table("connected_accounts").update({
            "connected": False,
            "updated_at": self._utc_now_iso(),
        }).eq("user_id", user_id).eq("provider", provider).execute()

    # -------------------------
    # NORMALIZE AUTH RESPONSE
    # Converts the SDK response object into a predictable dict for the UI.
    # -------------------------
    def _normalize_auth_response(self, response: Any) -> Dict[str, Any]:
        user = getattr(response, "user", None)
        session = getattr(response, "session", None)

        user_metadata = {}
        if user is not None:
            user_metadata = getattr(user, "user_metadata", None) or {}
            email = getattr(user, "email", "") or ""
            user_id = getattr(user, "id", "") or ""
        else:
            email = ""
            user_id = ""

        return {
            "user": user,
            "session": session,
            "email": email,
            "user_id": user_id,
            "access_token": getattr(session, "access_token", "") if session is not None else "",
            "refresh_token": getattr(session, "refresh_token", "") if session is not None else "",
            "full_name": (
                user_metadata.get("full_name")
                or user_metadata.get("name")
                or self._fallback_name_from_email(email)
            ),
            "email_confirmed": bool(getattr(user, "email_confirmed_at", None)) if user is not None else False,
        }

    # -------------------------
    # FALLBACK NAME
    # Derives a simple display name when no metadata is available.
    # -------------------------
    def _fallback_name_from_email(self, email: str) -> str:
        email = (email or "").strip()
        if "@" not in email:
            return "User"
        return email.split("@", 1)[0].replace(".", " ").replace("_", " ").title() or "User"

    # -------------------------
    # UTC NOW ISO
    # Returns an ISO timestamp suitable for Supabase timestamptz columns.
    # -------------------------
    def _utc_now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
