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
from typing import Any, Dict, List, Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.backend.core.AutoReturn_Gmail_Automation import OAuthManager
from src.backend.models.event_models import EventCandidate
from src.backend.utils.timezone_utils import normalize_timezone


# Calendar write scope is sufficient for insert/read conflict checks.
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar"
]


class CalendarService:
    """
    Service for Google Calendar insertion, conflict detection, and ICS export.
    """

    # -------------------------
    # INIT
    # Initializes the class instance and sets up default routing or UI states.
    # -------------------------
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self.client_secret_path = os.path.join(self.data_dir, "client_secret.json")
        self.token_path = os.path.join(self.data_dir, "token.json")

        self.oauth_manager: Optional[OAuthManager] = None
        self.service = None
        self.is_connected = False

    # -------------------------
    # CONNECT
    # Establishes connections for the operation.
    # -------------------------
    def connect(self, allow_flow: bool = True) -> Tuple[bool, str]:
        """Initialize OAuth credentials and Calendar API client."""
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

    # -------------------------
    # CREATE EVENTS
    # Instantiates and creates events.
    # -------------------------
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
                # Convert our internal candidate model to Google event payload.
                payload = self._event_to_payload(ev)
                self.service.events().insert(calendarId=calendar_id, body=payload).execute()
                created += 1
            except HttpError as exc:
                errors.append(str(exc))
            except Exception as exc:
                errors.append(str(exc))

        return created, errors

    # -------------------------
    # FIND CONFLICTS
    # Handles find functionality for conflicts.
    # -------------------------
    def find_conflicts(self, ev: EventCandidate, calendar_id: str = "primary") -> List[Dict[str, Any]]:
        """Find existing Google Calendar events overlapping with a candidate event."""
        if not self.is_connected or not self.service:
            return []

        start_dt, end_dt, tz_name = self._event_time_bounds(ev)
        time_min = start_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        time_max = end_dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        try:
            response = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=25,
            ).execute()
        except Exception:
            return []

        conflicts: List[Dict[str, Any]] = []
        for item in response.get("items", []):
            if item.get("status") == "cancelled":
                continue

            # Normalize Google event bounds before overlap checks.
            existing_start, existing_end = self._google_event_bounds(item, tz_name)
            if existing_start is None or existing_end is None:
                continue

            # Two ranges overlap if each starts before the other ends.
            overlaps = (start_dt < existing_end) and (existing_start < end_dt)
            if not overlaps:
                continue

            conflicts.append({
                "id": item.get("id", ""),
                "summary": item.get("summary", "(No title)"),
                "htmlLink": item.get("htmlLink", ""),
                "start": existing_start,
                "end": existing_end,
            })

        return conflicts

    # -------------------------
    # EXPORT ICS
    # Handles export functionality for ics.
    # -------------------------
    def export_ics(self, events: List[EventCandidate], output_dir: str) -> Tuple[str, int]:
        """Export events to an ICS file and return the file path."""
        os.makedirs(output_dir, exist_ok=True)

        cal_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//AutoReturn//Calendar Export//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]
        # Append one VEVENT block per candidate event.
        cal_lines.extend(self._to_ics_event_lines(ev) for ev in events)
        cal_lines.append("END:VCALENDAR")

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(output_dir, f"autoreturn_events_{ts}.ics")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\r\n".join(cal_lines) + "\r\n")

        return file_path, len(events)

    # -------------------------
    # TO ICS EVENT LINES
    # Handles to functionality for ics event lines.
    # -------------------------
    def _to_ics_event_lines(self, ev: EventCandidate) -> str:
        """Convert one event candidate to a VEVENT block string."""
        ev.ensure_end()
        tz_name = normalize_timezone(ev.timezone)

        start_dt = ev.start_dt
        end_dt = ev.end_dt or ev.start_dt

        # Ensure timezone-aware datetimes for timed events.
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=ZoneInfo(tz_name))
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=ZoneInfo(tz_name))

        uid = f"{ev.source}-{ev.source_id}-{int(start_dt.timestamp())}@autoreturn"
        dtstamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dtstamp}",
        ]

        if ev.all_day:
            lines.append(f"DTSTART;VALUE=DATE:{start_dt.date().strftime('%Y%m%d')}")
            lines.append(f"DTEND;VALUE=DATE:{end_dt.date().strftime('%Y%m%d')}")
        else:
            lines.append(
                f"DTSTART;TZID={tz_name}:{start_dt.strftime('%Y%m%dT%H%M%S')}"
            )
            lines.append(
                f"DTEND;TZID={tz_name}:{end_dt.strftime('%Y%m%dT%H%M%S')}"
            )

        lines.append(f"SUMMARY:{self._ics_escape(ev.title)}")
        if ev.description:
            lines.append(f"DESCRIPTION:{self._ics_escape(ev.description)}")
        if ev.location:
            lines.append(f"LOCATION:{self._ics_escape(ev.location)}")

        lines.append("END:VEVENT")
        return "\r\n".join(lines)

    # -------------------------
    # ICS ESCAPE
    # Handles ics functionality for escape.
    # -------------------------
    @staticmethod
    def _ics_escape(value: str) -> str:
        """Escape text according to ICS content line rules."""
        return (
            value.replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace("\r", "")
            .replace(",", "\\,")
            .replace(";", "\\;")
        )

    # -------------------------
    # EVENT TO PAYLOAD
    # Handles event functionality for to payload.
    # -------------------------
    def _event_to_payload(self, ev: EventCandidate) -> dict:
        """Map an internal event candidate to Google Calendar API payload format."""
        ev.ensure_end()
        tz_name = normalize_timezone(ev.timezone)

        start_dt = ev.start_dt
        end_dt = ev.end_dt or ev.start_dt

        # Ensure timezone-aware datetimes before generating ISO strings.
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
            # Google expects date-only values for all-day events.
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

    # -------------------------
    # EVENT TIME BOUNDS
    # Handles event functionality for time bounds.
    # -------------------------
    def _event_time_bounds(self, ev: EventCandidate) -> Tuple[datetime, datetime, str]:
        """Return timezone-aware start/end bounds for conflict checking."""
        ev.ensure_end()
        tz_name = normalize_timezone(ev.timezone)

        start_dt = ev.start_dt
        end_dt = ev.end_dt or ev.start_dt
        if start_dt.tzinfo is None:
            start_dt = start_dt.replace(tzinfo=ZoneInfo(tz_name))
        if end_dt.tzinfo is None:
            end_dt = end_dt.replace(tzinfo=ZoneInfo(tz_name))

        if ev.all_day:
            start_dt = datetime.combine(start_dt.date(), datetime.min.time(), tzinfo=ZoneInfo(tz_name))
            end_dt = datetime.combine(end_dt.date(), datetime.min.time(), tzinfo=ZoneInfo(tz_name))
            if end_dt <= start_dt:
                end_dt = start_dt.replace(hour=23, minute=59)

        return start_dt, end_dt, tz_name

    # -------------------------
    # GOOGLE EVENT BOUNDS
    # Handles google functionality for event bounds.
    # -------------------------
    def _google_event_bounds(self, item: Dict[str, Any], fallback_tz: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """Parse Google Calendar event start/end payload into datetimes."""
        start_data = item.get("start", {}) or {}
        end_data = item.get("end", {}) or {}

        start = self._parse_google_dt(start_data, fallback_tz)
        end = self._parse_google_dt(end_data, fallback_tz)
        return start, end

    # -------------------------
    # PARSE GOOGLE DT
    # Extracts and parses google dt.
    # -------------------------
    @staticmethod
    def _parse_google_dt(value: Dict[str, Any], fallback_tz: str) -> Optional[datetime]:
        date_time = value.get("dateTime")
        if date_time:
            try:
                dt = datetime.fromisoformat(str(date_time).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=ZoneInfo(fallback_tz))
                return dt
            except Exception:
                return None

        all_day_date = value.get("date")
        if all_day_date:
            try:
                date_obj = datetime.fromisoformat(all_day_date).date()
                return datetime.combine(date_obj, datetime.min.time(), tzinfo=ZoneInfo(fallback_tz))
            except Exception:
                return None

        return None
