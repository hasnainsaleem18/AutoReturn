"""Helpers for reusing message analysis across sync cycles."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


ANALYSIS_CACHE_FIELDS = (
    "priority",
    "ai_priority_score",
    "ai_tasks",
    "ai_events",
    "ai_events_count",
    "ai_tone_signal",
    "summary",
    "ai_analysis",
)


def build_message_analysis_cache(
    messages: Iterable[Dict[str, Any]],
    source: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """Build a message-id keyed cache of fields that are expensive to compute."""
    cache: Dict[str, Dict[str, Any]] = {}
    for message in messages or []:
        if source and str(message.get("source", "")).lower() != source.lower():
            continue

        message_id = _message_id(message)
        if not message_id:
            continue

        cached = {
            field: message[field]
            for field in ANALYSIS_CACHE_FIELDS
            if field in message and _cache_value_is_meaningful(field, message[field])
        }
        if cached:
            cache[message_id] = cached

    return cache


def extract_analysis_cache(parameters: Dict[str, Any], source: str) -> Dict[str, Dict[str, Any]]:
    """Read direct or source-scoped analysis cache from an agent request."""
    parameters = parameters or {}
    cache: Dict[str, Dict[str, Any]] = {}

    direct_cache = parameters.get("analysis_cache")
    if isinstance(direct_cache, dict):
        cache.update(_normalize_cache_keys(direct_cache))

    cache_by_source = parameters.get("analysis_cache_by_source")
    if isinstance(cache_by_source, dict):
        source_cache = cache_by_source.get(source)
        if isinstance(source_cache, dict):
            cache.update(_normalize_cache_keys(source_cache))

    return cache


def apply_cached_analysis(message: Dict[str, Any], analysis_cache: Dict[str, Dict[str, Any]]) -> bool:
    """Copy cached analysis fields onto a fetched message when available."""
    message_id = _message_id(message)
    if not message_id:
        return False

    cached = analysis_cache.get(message_id)
    if not isinstance(cached, dict):
        return False

    applied = False
    for field in ANALYSIS_CACHE_FIELDS:
        if field in cached and _cache_value_is_meaningful(field, cached[field]):
            message[field] = cached[field]
            applied = True

    return applied


def has_priority_analysis(message: Dict[str, Any]) -> bool:
    """Return True only when the full priority engine has already run."""
    return bool(str(message.get("ai_priority_score", "") or "").strip())


def has_task_analysis(message: Dict[str, Any]) -> bool:
    """Return True when task classification has already been stored."""
    tasks = message.get("ai_tasks")
    return isinstance(tasks, list) and len(tasks) > 0


def has_event_analysis(message: Dict[str, Any]) -> bool:
    """Return True even when the previous valid result was an empty event list."""
    return "ai_events" in message


def has_tone_analysis(message: Dict[str, Any]) -> bool:
    """Return True when Slack tone analysis has already been stored."""
    return bool(str(message.get("ai_tone_signal", "") or "").strip())


def _message_id(message: Dict[str, Any]) -> str:
    return str(message.get("id", "") or "").strip()


def _normalize_cache_keys(cache: Dict[Any, Any]) -> Dict[str, Dict[str, Any]]:
    normalized: Dict[str, Dict[str, Any]] = {}
    for key, value in cache.items():
        cache_key = str(key or "").strip()
        if cache_key and isinstance(value, dict):
            normalized[cache_key] = value
    return normalized


def _cache_value_is_meaningful(field: str, value: Any) -> bool:
    if field == "ai_events":
        return isinstance(value, list)
    if field == "ai_events_count":
        return isinstance(value, int)
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return value is not None
