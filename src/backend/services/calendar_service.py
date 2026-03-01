# -------------------------
# CALENDAR SERVICE
# -------------------------
"""
Google Calendar + ICS export service.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import List, Optional, Tuple

from ics import Calendar, Event
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.backend.core.AutoReturn_Gmail_Automation import OAuthManager
from src.backend.models.event_models import EventCandidate
from src.backend.utils.timezone_utils import normalize_timezone


CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar"
]


class CalendarService:
    """Service for Google Calendar insertion and ICS export."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self.client_secret_path = os.path.join(self.data_dir, "client_secret.json")
        self.token_path = os.path.join(self.data_dir, "token.json")

        self.oauth_manager: Optional[OAuthManager] = None
        self.service = None
        self.is_connected = False

    def connect(self, allow_flow: bool = True) -> Tuple[bool, str]:
        if not os.path.exists(self.client_secret_path):
            return False, "Upload client_secret.json in Settings before connecting Calendar."

        self.oauth_manager = OAuthManager(
            client_secret_path=self.client_secret_path,
            token_path=self.token_path,
            scopes=CALENDAR_SCOPES
        )

        success = self.oauth_manager.load_or_generate_token(allow_flow=allow_flow)
        if not success:
            return False, "Calendar authorization failed. Please re-authenticate."

        try:
            self.service = build("calendar", "v3", credentials=self.oauth_manager.creds)
            self.is_connected = True
            return True, "Connected to Google Calendar."
        except Exception as exc:
            return False, f"Calendar connection failed: {exc}"

    def create_events(self, events: List[EventCandidate], calendar_id: str = "primary") -> Tuple[int, List[str]]:
        """Insert events into Google Calendar.

        Returns: (created_count, errors)
        """
        if not self.is_connected or not self.service:
            return 0, ["Calendar service not connected."]

        errors = []
        created = 0

        for ev in events:
            try:
                payload = self._event_to_payload(ev)
                self.service.events().insert(calendarId=calendar_id, body=payload).execute()
                created += 1
            except HttpError as exc:
                errors.append(str(exc))
            except Exception as exc:
                errors.append(str(exc))

        return created, errors

    def export_ics(self, events: List[EventCandidate], output_dir: str) -> Tuple[str, int]:
        """Export events to an ICS file and return the file path."""
        os.makedirs(output_dir, exist_ok=True)

        cal = Calendar()
        for ev in events:
            ics_event = Event()
            ics_event.name = ev.title
            ics_event.begin = ev.start_dt
            if ev.end_dt:
                ics_event.end = ev.end_dt
            ics_event.location = ev.location or ""
            ics_event.description = ev.description or ""
            cal.events.add(ics_event)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(output_dir, f"autoreturn_events_{ts}.ics")
        with open(file_path, "w") as f:
            f.writelines(cal.serialize_iter())

        return file_path, len(events)

    def _event_to_payload(self, ev: EventCandidate) -> dict:
        ev.ensure_end()
        tz_name = normalize_timezone(ev.timezone)

        start_dt = ev.start_dt
        end_dt = ev.end_dt or ev.start_dt

        # Ensure timezone-aware datetimes
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=ZoneInfo(tz_name))
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=ZoneInfo(tz_name))

        start = {
            "dateTime": start_dt.isoformat(),
            "timeZone": tz_name
        }
        end = {
            "dateTime": end_dt.isoformat(),
            "timeZone": tz_name
        }

        if ev.all_day:
            start = {"date": ev.start_dt.date().isoformat()}
            end_date = (ev.end_dt or ev.start_dt).date().isoformat()
            end = {"date": end_date}

        payload = {
            "summary": ev.title,
            "description": ev.description or "",
            "location": ev.location or "",
            "start": start,
            "end": end,
            "extendedProperties": {
                "private": {
                    "autoreturn_source_id": ev.source_id,
                    "autoreturn_source": ev.source
                }
            }
        }

        if ev.recurrence:
            payload["recurrence"] = [ev.recurrence]

        return payload
