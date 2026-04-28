#!/usr/bin/env python3
# -------------------------
# EVENT EXTRACTOR TEST
# -------------------------
"""Basic tests for deterministic event extraction."""

# -------------------------
# IMPORTS
# -------------------------
import asyncio

from src.backend.core.event_extractor import EventExtractor


# -------------------------
# RUN EXTRACTION TEST
# Creates deterministic extractor instance and runs async extraction
# for a single message payload.
# -------------------------
def run_test(message):
    extractor = EventExtractor(ai_service=None, enable_llm_fallback=False)
    return asyncio.run(extractor.extract_from_message(message))


# -------------------------
# MAIN TEST ENTRY
# Runs two sample message scenarios and prints extracted event counts.
# -------------------------
def main():
    msg1 = {
        "id": "m1",
        "source": "gmail",
        "subject": "Interview with Ali",
        "full_content": "Interview tomorrow at 3pm in Room 401."
    }

    msg2 = {
        "id": "m2",
        "source": "gmail",
        "subject": "Birthday reminder",
        "full_content": "Sara's birthday is on May 12."
    }

    results1 = run_test(msg1)
    results2 = run_test(msg2)

    print("Test 1 events:", len(results1))
    print("Test 2 events:", len(results2))


if __name__ == "__main__":
    main()
