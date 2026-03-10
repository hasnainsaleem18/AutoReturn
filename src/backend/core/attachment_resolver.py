# -------------------------
# ATTACHMENT RESOLVER
# -------------------------
"""
Attachment resolver for automation flows.

Finds relevant local files from user-allowed paths when a message requests files.
"""

# -------------------------
# IMPORTS
# -------------------------
import os
import re
from typing import List, Dict


# -------------------------
# ATTACHMENT RESOLVER CLASS
# Rule-based helper that detects attachment requests and resolves
# likely local files from user-allowed paths.
# -------------------------
class AttachmentResolver:
    """Resolve attachments from allowed file/folder paths using filename heuristics."""

    # Verbs that usually imply the sender is asking for something to be shared.
    _VERBS = (
        "attach",
        "attached",
        "attachment",
        "send",
        "share",
        "provide",
        "forward",
        "upload",
    )

    # Nouns commonly used when asking for documents/files.
    _NOUNS = (
        "file",
        "files",
        "document",
        "documents",
        "doc",
        "pdf",
        "report",
        "invoice",
        "resume",
        "image",
        "screenshot",
        "sheet",
        "spreadsheet",
        "presentation",
        "zip",
    )

    # Explicit filename detector (e.g., "Q3 report.pdf") with common attachment extensions.
    _FILENAME_RE = re.compile(r"\b[\w\-. ]+\.(pdf|doc|docx|xls|xlsx|ppt|pptx|csv|txt|zip|png|jpg|jpeg)\b", re.I)

    # Generic words removed from query token extraction to reduce noisy matches.
    _STOPWORDS = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "you",
        "your",
        "please",
        "kindly",
        "can",
        "could",
        "would",
        "need",
        "needed",
        "share",
        "send",
        "attach",
        "file",
        "files",
        "document",
        "documents",
    }

    # -------------------------
    # MAIN RESOLVE METHOD
    # End-to-end flow:
    # 1) Detect whether the message is requesting an attachment.
    # 2) Collect files from user-allowed paths.
    # 3) Score and select best candidate files.
    # 4) Return selected attachments or ambiguity details.
    # -------------------------
    def resolve(self, message: dict, allowed_paths: List[str], max_auto_attachments: int = 3) -> Dict:
        """Return a resolution plan for automation attachment handling."""
        # Build normalized searchable text from multiple message fields.
        text = self._message_text(message)

        # Quick intent gate: if no attachment request signal, stop early.
        requested = self._looks_like_attachment_request(text)
        if not requested:
            return {
                "requested": False,
                "attachments": [],
                "reason": "No attachment request detected.",
                "candidates": [],
            }

        # Respect automation safety setting that can disable auto-attachment entirely.
        if max_auto_attachments <= 0:
            return {
                "requested": True,
                "attachments": [],
                "reason": "Attachment request detected, but max auto attachments is set to 0.",
                "candidates": [],
            }

        # Discover readable files only within user-approved directories/files.
        files = self._collect_allowed_files(allowed_paths)
        if not files:
            return {
                "requested": True,
                "attachments": [],
                "reason": "Attachment request detected, but no readable files found in allowed paths.",
                "candidates": [],
            }

        # Extract explicit filename mentions and broader keyword tokens for fuzzy matching.
        explicit_names = [m.group(0).strip().lower() for m in self._FILENAME_RE.finditer(text)]
        query_tokens = self._query_tokens(text)

        # Score every candidate file by explicit-name and token overlap.
        scored = self._score_files(files, query_tokens, explicit_names)
        if not scored:
            return {
                "requested": True,
                "attachments": [],
                "reason": "Attachment request detected, but no relevant file match was found.",
                "candidates": [],
            }

        # If several files tie at low confidence, force manual review to avoid wrong sends.
        best_score = scored[0][1]
        candidates = [path for path, score in scored if score == best_score][:5]
        if len(candidates) > 1 and best_score < 7:
            names = ", ".join(os.path.basename(p) for p in candidates[:3])
            return {
                "requested": True,
                "attachments": [],
                "reason": f"Multiple possible files found ({names}). Please choose manually.",
                "candidates": candidates,
            }

        # High-confidence path: auto-select top results (bounded by policy limit).
        selected = [path for path, _ in scored[:max_auto_attachments]]
        return {
            "requested": True,
            "attachments": selected,
            "reason": f"Resolved {len(selected)} attachment(s).",
            "candidates": [path for path, _ in scored[:5]],
        }

    # -------------------------
    # BUILD MESSAGE TEXT
    # Merges subject/body preview fields into one lowercase string so
    # request detection and token extraction work consistently.
    # -------------------------
    def _message_text(self, message: dict) -> str:
        parts = [
            str(message.get("subject", "")),
            str(message.get("full_content", "")),
            str(message.get("content_preview", "")),
            str(message.get("preview", "")),
        ]
        return " ".join(parts).strip().lower()

    # -------------------------
    # REQUEST DETECTOR
    # Detects likely attachment intent using:
    # - Verb + noun pattern (e.g., "send report")
    # - Explicit filename mention (e.g., "budget.xlsx")
    # -------------------------
    def _looks_like_attachment_request(self, text: str) -> bool:
        if not text:
            return False
        has_verb = any(v in text for v in self._VERBS)
        has_noun = any(n in text for n in self._NOUNS)
        return has_verb and has_noun or bool(self._FILENAME_RE.search(text))

    # -------------------------
    # QUERY TOKEN BUILDER
    # Produces de-duplicated searchable tokens from message text by
    # removing stopwords and trivial numeric-only terms.
    # -------------------------
    def _query_tokens(self, text: str) -> List[str]:
        words = re.findall(r"[a-z0-9]{3,}", text.lower())
        tokens = []
        for word in words:
            if word in self._STOPWORDS:
                continue
            if word.isdigit():
                continue
            tokens.append(word)
        return list(dict.fromkeys(tokens))

    # -------------------------
    # FILE COLLECTOR
    # Walks all allowed file paths/directories and returns a bounded
    # list of readable file candidates for scoring.
    # -------------------------
    def _collect_allowed_files(self, allowed_paths: List[str], max_files: int = 2000) -> List[str]:
        files: List[str] = []
        for raw_path in allowed_paths or []:
            path = os.path.expanduser(str(raw_path).strip())
            if not path:
                continue
            if os.path.isfile(path):
                files.append(path)
            elif os.path.isdir(path):
                for root, _, names in os.walk(path):
                    for name in names:
                        file_path = os.path.join(root, name)
                        if os.path.isfile(file_path):
                            files.append(file_path)
                            if len(files) >= max_files:
                                return files
            if len(files) >= max_files:
                break
        return files

    # -------------------------
    # FILE SCORER
    # Ranking strategy:
    # - Explicit filename exact match: strong boost
    # - Explicit filename partial match: medium boost
    # - Query token in filename: incremental boosts
    # Returns candidates sorted by descending relevance.
    # -------------------------
    def _score_files(self, files: List[str], tokens: List[str], explicit_names: List[str]) -> List[tuple]:
        scored = []
        for path in files:
            name = os.path.basename(path).lower()
            score = 0

            if explicit_names:
                for explicit in explicit_names:
                    if explicit == name:
                        score += 20
                    elif explicit in name:
                        score += 12

            for token in tokens:
                if token in name:
                    score += 2

            if score > 0:
                scored.append((path, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        return scored
