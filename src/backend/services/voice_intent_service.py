# -------------------------
# VOICE INTENT SERVICE
# -------------------------
"""
Natural-language voice intent parsing for AutoReturn.

The service turns Whisper text into a bounded, structured action. It uses a
small deterministic parser first for common send/reply phrasing, then asks the
local Ollama service for strict JSON when available.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError


class VoiceIntent(BaseModel):
    """Structured action produced from a natural voice command."""

    action: str = Field(default="unknown")
    channel: str = Field(default="any")
    recipient: str = Field(default="")
    message: str = Field(default="")
    query: str = Field(default="")
    target: str = Field(default="")
    index: Optional[int] = None
    send_mode: str = Field(default="review")


class VoiceIntentService:
    """Parse flexible voice commands into safe, executable intents."""

    ALLOWED_ACTIONS = {
        "filter_messages",
        "search_messages",
        "open_settings",
        "open_notifications",
        "next_page",
        "previous_page",
        "reply_to_sender",
        "send_message",
        "draft_reply",
        "summarize_message",
        "open_message",
        "show_voice_history",
        "undo_last_send",
        "sync_gmail",
        "sync_slack",
        "sync_all",
        "unknown",
    }
    ALLOWED_CHANNELS = {"gmail", "slack", "any"}

    def __init__(self, ai_service=None):
        self.ai_service = ai_service

    def parse(self, text: str) -> VoiceIntent:
        cleaned = self._clean_text(text)
        if not cleaned:
            return VoiceIntent(action="unknown")

        deterministic = self._parse_deterministic(cleaned)
        if deterministic.action != "unknown":
            return deterministic

        llm_intent = self._parse_with_llm(cleaned)
        if llm_intent and llm_intent.action != "unknown":
            return llm_intent
        return deterministic

    def parse_plan(self, text: str) -> List[VoiceIntent]:
        """Parse a voice command into one or more sequential intents."""
        cleaned = self._clean_text(text)
        if not cleaned:
            return [VoiceIntent(action="unknown")]

        if self._looks_like_multi_step(cleaned):
            llm_plan = self._parse_plan_with_llm(cleaned)
            if llm_plan:
                return llm_plan

            steps = []
            for segment in self._split_plan_segments(cleaned):
                intent = self.parse(segment)
                if intent.action != "unknown":
                    steps.append(intent)
            if steps:
                return steps

        return [self.parse(cleaned)]

    def _parse_with_llm(self, text: str) -> Optional[VoiceIntent]:
        if not self.ai_service or not getattr(self.ai_service, "check_connection", lambda: False)():
            return None

        prompt = self._build_prompt(text)
        response = self.ai_service.generate_text(prompt, temperature=0.0, max_tokens=180)
        if not response:
            return None

        try:
            payload = self._extract_json_object(response)
            return self._coerce_intent(payload, raw_text=text)
        except Exception as exc:
            print(f"[VoiceIntentService] Could not parse LLM voice intent: {exc}")
            return None

    def _parse_plan_with_llm(self, text: str) -> Optional[List[VoiceIntent]]:
        if not self.ai_service or not getattr(self.ai_service, "check_connection", lambda: False)():
            return None

        response = self.ai_service.generate_text(self._build_plan_prompt(text), temperature=0.0, max_tokens=420)
        if not response:
            return None

        try:
            payload = self._extract_json_object(response)
            steps = payload.get("steps") or []
            if not isinstance(steps, list):
                return None
            intents = [
                self._coerce_intent(step, raw_text=text)
                for step in steps
                if isinstance(step, dict)
            ]
            return [intent for intent in intents if intent.action != "unknown"] or None
        except Exception as exc:
            print(f"[VoiceIntentService] Could not parse LLM voice plan: {exc}")
            return None

    def _parse_deterministic(self, text: str) -> VoiceIntent:
        lowered = text.lower().strip()

        if re.search(r"\b(show|open|view)\s+(voice\s+)?(command\s+)?history\b", lowered):
            return VoiceIntent(action="show_voice_history")
        if re.search(r"\b(undo|delete|remove)\s+(the\s+)?(last\s+)?(sent\s+)?(message|send|slack\s+message)\b", lowered):
            return VoiceIntent(action="undo_last_send", channel="slack")
        if re.search(r"\b(open|show)\s+settings\b", lowered):
            return VoiceIntent(action="open_settings")
        if re.search(r"\b(show|open)\s+notifications?\b", lowered):
            return VoiceIntent(action="open_notifications")
        if re.search(r"\bnext\s+page\b", lowered):
            return VoiceIntent(action="next_page")
        if re.search(r"\b(previous|prev|back)\s+page\b", lowered):
            return VoiceIntent(action="previous_page")
        if re.search(r"\b(open|show|read|view)\s+(this|current|selected)\s+(message|email|mail)\b", lowered):
            return VoiceIntent(action="open_message", target="current")
        if re.search(r"\b(summarize|summary)\s+(this|current|selected)\s+(message|email|mail)\b", lowered):
            return VoiceIntent(action="summarize_message", target="current")
        if re.search(r"\b(summarize|summary)\s+(this|current|selected)\b", lowered):
            return VoiceIntent(action="summarize_message", target="current")
        if re.search(r"\bsync\s+(all|everything|messages)\b", lowered):
            return VoiceIntent(action="sync_all")
        if re.search(r"\bsync\s+gmail\b|\bcheck\s+(gmail|email)\b", lowered):
            return VoiceIntent(action="sync_gmail")
        if re.search(r"\bsync\s+slack\b|\bcheck\s+slack\b", lowered):
            return VoiceIntent(action="sync_slack")

        filter_match = re.search(r"\bshow\s+(all|gmail|email|slack|urgent|high priority)\b", lowered)
        if filter_match:
            target = filter_match.group(1)
            if target == "email":
                target = "gmail"
            if target == "high priority":
                target = "urgent"
            return VoiceIntent(action="filter_messages", target=target)

        search_match = re.search(r"\b(?:search|find|look for)\s+(?:for\s+)?(.+)$", text, re.IGNORECASE)
        if search_match:
            return VoiceIntent(
                action="search_messages",
                query=self._clean_target(search_match.group(1)),
            )

        context_draft_match = re.search(
            r"\b(?:draft|write)\s+(?:a\s+)?(?:reply|response)?\s*(?:for|to)?\s+"
            r"(?:this|current|selected)(?:\s+(?:message|email|mail))?(?:\s+(?:saying|that|with message)\s+(.+))?$",
            text,
            re.IGNORECASE,
        )
        if context_draft_match:
            return VoiceIntent(
                action="draft_reply",
                target="current",
                message=self._clean_message(context_draft_match.group(1) or ""),
                send_mode="review",
            )

        draft_match = re.search(
            r"\b(?:draft|write)\s+(?:a\s+)?(?:reply|response)\s+(?:to|for)\s+(.+)$",
            text,
            re.IGNORECASE,
        )
        if draft_match:
            recipient, message = self._split_recipient_and_message(draft_match.group(1))
            if not recipient:
                return VoiceIntent(action="unknown")
            return VoiceIntent(
                action="draft_reply",
                recipient=recipient,
                message=message,
                send_mode="review",
            )

        context_reply_match = re.search(
            r"\b(?:reply|respond|send\s+(?:a\s+)?reply)\s+(?:to|for)?\s*"
            r"(?:this|current|selected)(?:\s+(?:message|email|mail))?(?:\s+(?:saying|that|with message|and say|and saying|reply is|the reply is)\s+(.+))?$",
            text,
            re.IGNORECASE,
        )
        if context_reply_match:
            return VoiceIntent(
                action="reply_to_sender",
                target="current",
                message=self._clean_message(context_reply_match.group(1) or ""),
                send_mode="review",
            )

        channel_send_to_match = re.search(
            r"\bsend\s+(?:a\s+)?(gmail|email|mail|slack)\s+(?:message|dm|email|mail)?\s*(?:to|for)\s+(.+?)\s*"
            r"(?:saying|that|with message|and say|and saying)\s+(.+)$",
            text,
            re.IGNORECASE,
        )
        if channel_send_to_match:
            return VoiceIntent(
                action="send_message",
                channel=self._normalize_channel(channel_send_to_match.group(1)),
                recipient=self._clean_target(channel_send_to_match.group(2)),
                message=self._clean_message(channel_send_to_match.group(3)),
                send_mode="review",
            )

        reply_match = re.search(
            r"\b(?:reply|respond|send\s+(?:a\s+)?reply)\s+(?:to|for)\s+(.+)$",
            text,
            re.IGNORECASE,
        )
        if reply_match:
            recipient, message = self._split_recipient_and_message(reply_match.group(1))
            if not recipient:
                return VoiceIntent(action="unknown")
            return VoiceIntent(
                action="reply_to_sender",
                recipient=recipient,
                message=message,
                send_mode="review",
            )

        send_to_match = re.search(
            r"\bsend\s+(?:a\s+)?(?:message|dm|email|mail)\s+(?:to|for)\s+(.+?)\s*"
            r"(?:saying|that|with message|and say|and saying)\s+(.+)$",
            text,
            re.IGNORECASE,
        )
        if send_to_match:
            return VoiceIntent(
                action="send_message",
                channel="any",
                recipient=self._clean_target(send_to_match.group(1)),
                message=self._clean_message(send_to_match.group(2)),
                send_mode="review",
            )

        direct_send_match = re.search(
            r"\bsend\s+(.+?)\s+(?:(?:a|an|the)\s+)?(?:(gmail|email|slack)\s+)?(?:message|dm|email|mail)?\s*"
            r"(?:saying|that|with message|and say|and saying)\s+(.+)$",
            text,
            re.IGNORECASE,
        )
        if direct_send_match:
            channel = self._normalize_channel(direct_send_match.group(2) or "any")
            return VoiceIntent(
                action="send_message",
                channel=channel,
                recipient=self._clean_target(direct_send_match.group(1)),
                message=self._clean_message(direct_send_match.group(3)),
                send_mode="review",
            )

        send_match = re.search(
            r"\bsend\s+(?:a\s+)?(?:message|dm|email)?\s*(?:to)?\s+(.+)$",
            text,
            re.IGNORECASE,
        )
        if send_match:
            recipient, message = self._split_recipient_and_message(send_match.group(1))
            if not recipient:
                return VoiceIntent(action="unknown")
            return VoiceIntent(
                action="send_message",
                recipient=recipient,
                message=message,
                send_mode="review",
            )

        return VoiceIntent(action="unknown")

    def _coerce_intent(self, payload: Dict[str, Any], raw_text: str) -> VoiceIntent:
        data = dict(payload)
        data["action"] = str(data.get("action") or "unknown").strip().lower()
        data["channel"] = str(data.get("channel") or "any").strip().lower()
        data["send_mode"] = "review"

        if data["action"] not in self.ALLOWED_ACTIONS:
            data["action"] = "unknown"
        if data["channel"] not in self.ALLOWED_CHANNELS:
            data["channel"] = "any"

        try:
            intent = VoiceIntent(**data)
        except ValidationError:
            intent = VoiceIntent(action="unknown")

        is_current_target = (intent.target or "").strip().lower() in {"current", "this", "selected"}
        if intent.action in {"reply_to_sender", "send_message", "draft_reply"} and not intent.recipient and not is_current_target:
            fallback = self._parse_deterministic(raw_text)
            if fallback.recipient:
                return fallback
        return intent

    def _build_prompt(self, text: str) -> str:
        return f"""You convert AutoReturn desktop voice commands into strict JSON.

Return exactly one JSON object and no markdown.

Allowed actions:
filter_messages, search_messages, open_settings, open_notifications,
next_page, previous_page, reply_to_sender, send_message, draft_reply,
summarize_message, open_message, show_voice_history, undo_last_send,
sync_gmail, sync_slack, sync_all, unknown.

Allowed channels: gmail, slack, any.
For send/reply/draft commands, always set send_mode to "review".
Never invent recipients or message text.

JSON schema:
{{
  "action": "reply_to_sender",
  "channel": "any",
  "recipient": "Hasnain",
  "message": "here is the update",
  "query": "",
  "target": "",
  "index": null,
  "send_mode": "review"
}}

Examples:
Command: reply to Hasnain saying here is the update
JSON: {{"action":"reply_to_sender","channel":"any","recipient":"Hasnain","message":"here is the update","query":"","target":"","index":null,"send_mode":"review"}}

Command: send Ali a Slack message that I will join late
JSON: {{"action":"send_message","channel":"slack","recipient":"Ali","message":"I will join late","query":"","target":"","index":null,"send_mode":"review"}}

Command: show urgent Gmail messages
JSON: {{"action":"filter_messages","channel":"gmail","recipient":"","message":"","query":"","target":"urgent","index":null,"send_mode":"review"}}

Command: reply to this saying I will send it today
JSON: {{"action":"reply_to_sender","channel":"any","recipient":"","message":"I will send it today","query":"","target":"current","index":null,"send_mode":"review"}}

Command: summarize this message
JSON: {{"action":"summarize_message","channel":"any","recipient":"","message":"","query":"","target":"current","index":null,"send_mode":"review"}}

Command: {text}
JSON:"""

    def _build_plan_prompt(self, text: str) -> str:
        return f"""You convert AutoReturn desktop voice commands into a strict JSON plan.

Return exactly one JSON object and no markdown.

The JSON object must be:
{{"steps":[INTENT_OBJECT, INTENT_OBJECT]}}

Use the same intent schema as single commands:
action, channel, recipient, message, query, target, index, send_mode.

Allowed actions:
filter_messages, search_messages, open_settings, open_notifications,
next_page, previous_page, reply_to_sender, send_message, draft_reply,
summarize_message, open_message, show_voice_history, undo_last_send,
sync_gmail, sync_slack, sync_all, unknown.

Allowed channels: gmail, slack, any.
For send/reply/draft commands, always set send_mode to "review".
Never invent recipients or message text.

Examples:
Command: show urgent messages and then summarize this message
JSON: {{"steps":[{{"action":"filter_messages","channel":"any","recipient":"","message":"","query":"","target":"urgent","index":null,"send_mode":"review"}},{{"action":"summarize_message","channel":"any","recipient":"","message":"","query":"","target":"current","index":null,"send_mode":"review"}}]}}

Command: sync gmail then show voice history
JSON: {{"steps":[{{"action":"sync_gmail","channel":"any","recipient":"","message":"","query":"","target":"","index":null,"send_mode":"review"}},{{"action":"show_voice_history","channel":"any","recipient":"","message":"","query":"","target":"","index":null,"send_mode":"review"}}]}}

Command: {text}
JSON:"""

    def _looks_like_multi_step(self, text: str) -> bool:
        return bool(re.search(r"\b(and then|then|after that|also|and also)\b", text, re.IGNORECASE))

    def _split_plan_segments(self, text: str) -> List[str]:
        parts = re.split(r"\b(?:and then|then|after that|also|and also)\b", text, flags=re.IGNORECASE)
        return [self._clean_text(part) for part in parts if self._clean_text(part)]

    def _split_recipient_and_message(self, value: str) -> tuple[str, str]:
        text = self._clean_text(value)
        patterns = (
            r"\s+(?:saying|that|with message|message|and say|and saying|reply is|the reply is)\s+",
            r"\s+colon\s+",
        )
        for pattern in patterns:
            parts = re.split(pattern, text, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                return self._clean_target(parts[0]), self._clean_message(parts[1])
        return self._clean_target(text), ""

    def _extract_json_object(self, response: str) -> Dict[str, Any]:
        text = (response or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
            text = re.sub(r"```$", "", text).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("No JSON object found")
        return json.loads(text[start : end + 1])

    def _clean_text(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", (text or "").strip())
        return cleaned.strip(" \t\r\n.,!?;:")

    def _clean_target(self, text: str) -> str:
        cleaned = self._clean_text(text)
        cleaned = re.sub(r"\b(?:please|now)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,!?:;\"'")
        if "@" in cleaned:
            return cleaned.lower()
        return " ".join(part.capitalize() for part in cleaned.split())

    def _clean_message(self, text: str) -> str:
        return self._clean_text(text).strip("\"'")

    def _normalize_channel(self, value: str) -> str:
        channel = (value or "any").strip().lower()
        if channel in {"email", "mail"}:
            return "gmail"
        if channel in self.ALLOWED_CHANNELS:
            return channel
        return "any"
