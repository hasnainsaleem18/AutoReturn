"""
Attachment resolver for automation flows.

Finds relevant local files from user-allowed paths when a message requests files.
"""

import os
import re
from typing import List, Dict


class AttachmentResolver:
    """Resolve attachments from allowed file/folder paths using filename heuristics."""

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
    _FILENAME_RE = re.compile(r"\b[\w\-. ]+\.(pdf|doc|docx|xls|xlsx|ppt|pptx|csv|txt|zip|png|jpg|jpeg)\b", re.I)

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

    def resolve(self, message: dict, allowed_paths: List[str], max_auto_attachments: int = 3) -> Dict:
        """Return a resolution plan for automation attachment handling."""
        text = self._message_text(message)
        requested = self._looks_like_attachment_request(text)
        if not requested:
            return {
                "requested": False,
                "attachments": [],
                "reason": "No attachment request detected.",
                "candidates": [],
            }

        if max_auto_attachments <= 0:
            return {
                "requested": True,
                "attachments": [],
                "reason": "Attachment request detected, but max auto attachments is set to 0.",
                "candidates": [],
            }

        files = self._collect_allowed_files(allowed_paths)
        if not files:
            return {
                "requested": True,
                "attachments": [],
                "reason": "Attachment request detected, but no readable files found in allowed paths.",
                "candidates": [],
            }

        explicit_names = [m.group(0).strip().lower() for m in self._FILENAME_RE.finditer(text)]
        query_tokens = self._query_tokens(text)

        scored = self._score_files(files, query_tokens, explicit_names)
        if not scored:
            return {
                "requested": True,
                "attachments": [],
                "reason": "Attachment request detected, but no relevant file match was found.",
                "candidates": [],
            }

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

        selected = [path for path, _ in scored[:max_auto_attachments]]
        return {
            "requested": True,
            "attachments": selected,
            "reason": f"Resolved {len(selected)} attachment(s).",
            "candidates": [path for path, _ in scored[:5]],
        }

    def _message_text(self, message: dict) -> str:
        parts = [
            str(message.get("subject", "")),
            str(message.get("full_content", "")),
            str(message.get("content_preview", "")),
            str(message.get("preview", "")),
        ]
        return " ".join(parts).strip().lower()

    def _looks_like_attachment_request(self, text: str) -> bool:
        if not text:
            return False
        has_verb = any(v in text for v in self._VERBS)
        has_noun = any(n in text for n in self._NOUNS)
        return has_verb and has_noun or bool(self._FILENAME_RE.search(text))

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
