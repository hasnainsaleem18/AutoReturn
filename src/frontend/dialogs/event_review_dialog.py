# -------------------------
# EVENT REVIEW DIALOG
# -------------------------
"""
Dialog for reviewing extracted events/tasks and adding them to calendar.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Dict, Any

import dateparser
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QMessageBox, QCheckBox, QHeaderView
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices

from src.backend.models.event_models import EventCandidate


class EventReviewDialog(QDialog):
    def __init__(self, events: List[Dict[str, Any]],
                 calendar_service,
                 auto_select_threshold: float = 0.85,
                 auto_add_high_confidence: bool = True,
                 ics_output_dir: str = "",
                 parent=None):
        super().__init__(parent)
        self.events = events or []
        self.calendar_service = calendar_service
        self.auto_select_threshold = auto_select_threshold
        self.auto_add_high_confidence = auto_add_high_confidence
        self.ics_output_dir = ics_output_dir

        self.setWindowTitle("Review Schedule Suggestions")
        self.setMinimumSize(840, 480)

        self._build_ui()
        self._auto_add_high_confidence()

    def _build_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel#title {
                font-size: 17px;
                font-weight: 700;
                color: #003135;
            }
            QLabel#subtitle {
                font-size: 13px;
                color: #024950;
            }
            QTableWidget {
                border: 1px solid #AFDDE5;
                border-radius: 8px;
                background-color: #ffffff;
                color: #003135;
                gridline-color: #AFDDE5;
            }
            QHeaderView::section {
                background-color: #AFDDE5;
                color: #003135;
                font-weight: 600;
                padding: 8px;
                border: none;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Review schedule suggestions before adding to Calendar")
        title.setObjectName("title")
        layout.addWidget(title)

        subtitle = QLabel("Choose the items that look correct. You can still edit time/title in Google Calendar after adding.")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.status_label = QLabel("")
        self.status_label.setObjectName("subtitle")
        layout.addWidget(self.status_label)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Select", "Suggested Title", "Starts", "Ends", "Category", "Confidence", "Why this score"
        ])
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked |
            QAbstractItemView.SelectedClicked |
            QAbstractItemView.EditKeyPressed
        )
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setRowCount(len(self.events))
        self.table.verticalHeader().setVisible(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        header.setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 70)
        self.table.setColumnWidth(2, 170)
        self.table.setColumnWidth(3, 170)
        self.table.setColumnWidth(5, 90)

        for row, ev in enumerate(self.events):
            confidence = float(ev.get("confidence", 0.0))

            checkbox = QCheckBox()
            checkbox.setChecked(confidence >= self.auto_select_threshold)
            self.table.setCellWidget(row, 0, checkbox)

            self.table.setItem(row, 1, self._make_item(ev.get("title", ""), editable=True))
            self.table.setItem(row, 2, self._make_item(self._fmt_dt(ev.get("start_dt")), editable=True))
            self.table.setItem(row, 3, self._make_item(self._fmt_dt(ev.get("end_dt")), editable=True))
            item_type = str(ev.get("item_type", "event")).lower()
            display_type = "To-do" if item_type == "task" else "Meeting"
            self.table.setItem(row, 4, self._make_item(display_type, editable=True))
            self.table.setItem(row, 5, self._make_item(f"{confidence:.2f}", editable=False))
            self.table.setItem(row, 6, self._make_item(self._confidence_reason(ev), editable=False))

        self.table.resizeRowsToContents()
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        add_btn = QPushButton("Add Selected to Calendar")
        add_btn.setObjectName("btnPrimary")
        add_btn.clicked.connect(self._handle_add_to_calendar)

        export_btn = QPushButton("Download .ics")
        export_btn.setObjectName("btnSecondary")
        export_btn.clicked.connect(self._handle_export_ics)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("btnSecondary")
        close_btn.clicked.connect(self.reject)

        btn_layout.addWidget(add_btn)
        btn_layout.addWidget(export_btn)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _fmt_dt(self, value) -> str:
        if not value:
            return ""
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        try:
            dt = datetime.fromisoformat(value)
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(value)

    def _parse_dt(self, value: str):
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except Exception:
            pass
        return dateparser.parse(value)

    def _make_item(self, text: str, editable: bool = True) -> QTableWidgetItem:
        item = QTableWidgetItem(str(text or ""))
        if not editable:
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _confidence_reason(self, ev: Dict[str, Any]) -> str:
        reasons = []
        confidence = float(ev.get("confidence", 0.0))
        if confidence >= 0.85:
            reasons.append("High confidence")
        elif confidence >= 0.65:
            reasons.append("Medium confidence")
        else:
            reasons.append("Low confidence")

        start_text = str(ev.get("start_dt", ""))
        if ":" in start_text or "T" in start_text:
            reasons.append("Specific time detected")
        else:
            reasons.append("Date-only detected")

        item_type = str(ev.get("item_type", "event")).lower()
        if item_type == "task":
            reasons.append("Task-style language found")
        else:
            reasons.append("Meeting/event-style language found")
        return " | ".join(reasons)

    def _selected_events(self) -> List[EventCandidate]:
        selected = []
        for row, ev in enumerate(self.events):
            widget = self.table.cellWidget(row, 0)
            if isinstance(widget, QCheckBox) and widget.isChecked():
                try:
                    updated = dict(ev)
                    title = (self.table.item(row, 1).text() if self.table.item(row, 1) else "").strip()
                    start_text = (self.table.item(row, 2).text() if self.table.item(row, 2) else "").strip()
                    end_text = (self.table.item(row, 3).text() if self.table.item(row, 3) else "").strip()
                    category = (self.table.item(row, 4).text() if self.table.item(row, 4) else "").strip().lower()

                    start_dt = self._parse_dt(start_text)
                    if not start_dt:
                        continue
                    end_dt = self._parse_dt(end_text) if end_text else None

                    updated["title"] = title or updated.get("title", "Untitled")
                    updated["start_dt"] = start_dt
                    updated["end_dt"] = end_dt
                    updated["item_type"] = "task" if category in ("task", "todo", "to-do") else "event"
                    has_explicit_time = (
                        ":" in start_text or
                        "am" in start_text.lower() or
                        "pm" in start_text.lower() or
                        "t" in start_text.lower()
                    )
                    updated["all_day"] = not has_explicit_time
                    if updated["all_day"] and updated["end_dt"] is None:
                        updated["end_dt"] = start_dt + timedelta(days=1)

                    selected.append(EventCandidate(**updated))
                except Exception:
                    continue
        return selected

    def _handle_add_to_calendar(self, auto_only: bool = False, override_events: List[EventCandidate] = None):
        selected = override_events if override_events is not None else self._selected_events()
        if not selected:
            if not auto_only:
                QMessageBox.information(self, "No Selection", "Please select at least one suggestion.")
            return

        if not self.calendar_service:
            if not auto_only:
                QMessageBox.warning(self, "Calendar", "Calendar service is not available.")
            return

        ok, msg = self.calendar_service.connect(allow_flow=True)
        if not ok:
            if not auto_only:
                QMessageBox.warning(self, "Calendar", msg)
            return

        selected_after_conflicts = self._resolve_conflicts(selected, interactive=not auto_only)
        if not selected_after_conflicts:
            if not auto_only:
                QMessageBox.information(self, "Calendar", "No items were added.")
            return

        created, errors = self.calendar_service.create_events(selected_after_conflicts)
        if auto_only:
            if created > 0:
                self.status_label.setText(f"Automatically added {created} high-confidence suggestions.")
            if errors:
                self.status_label.setText(f"Auto-add had errors: {errors}")
            return

        if errors:
            QMessageBox.warning(self, "Calendar", f"Added {created} items. Errors: {errors}")
        else:
            QMessageBox.information(self, "Calendar", f"Added {created} item(s) to Calendar.")

    def _resolve_conflicts(self, selected: List[EventCandidate], interactive: bool) -> List[EventCandidate]:
        """Resolve overlap conflicts with existing calendar items."""
        approved: List[EventCandidate] = []
        skipped_due_conflict = 0

        for ev in selected:
            conflicts = self.calendar_service.find_conflicts(ev)
            if not conflicts:
                approved.append(ev)
                continue

            if not interactive:
                skipped_due_conflict += 1
                continue

            decision = self._ask_conflict_decision(ev, conflicts)
            if decision == "add":
                approved.append(ev)
            elif decision == "skip":
                skipped_due_conflict += 1

        if skipped_due_conflict > 0:
            self.status_label.setText(f"Skipped {skipped_due_conflict} suggestion(s) due to schedule conflicts.")

        return approved

    def _ask_conflict_decision(self, ev: EventCandidate, conflicts: List[dict]) -> str:
        """Ask user how to handle a conflicting suggestion."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Time Conflict Found")
        dialog.resize(760, 420)
        dialog.setMinimumSize(680, 360)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("This suggestion overlaps with existing calendar item(s).")
        title.setObjectName("title")
        subtitle = QLabel(
            f"Suggestion: {ev.title}\n"
            f"Time: {self._fmt_dt(ev.start_dt)} - {self._fmt_dt(ev.end_dt)}"
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Existing Calendar Item", "Starts", "Ends"])
        table.setRowCount(len(conflicts))
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)

        for row, item in enumerate(conflicts):
            table.setItem(row, 0, QTableWidgetItem(item.get("summary", "(No title)")))
            table.setItem(row, 1, QTableWidgetItem(self._fmt_dt(item.get("start"))))
            table.setItem(row, 2, QTableWidgetItem(self._fmt_dt(item.get("end"))))

        if conflicts:
            table.selectRow(0)
        layout.addWidget(table)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open Selected Existing")
        open_btn.setObjectName("btnSecondary")
        skip_btn = QPushButton("Skip This Suggestion")
        skip_btn.setObjectName("btnSecondary")
        add_btn = QPushButton("Add Anyway")
        add_btn.setObjectName("btnPrimary")

        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        btn_row.addWidget(skip_btn)
        btn_row.addWidget(add_btn)
        layout.addLayout(btn_row)

        choice = {"value": "skip"}

        def _selected_conflict() -> dict:
            row = table.currentRow()
            if row < 0 or row >= len(conflicts):
                return conflicts[0]
            return conflicts[row]

        def _open_selected():
            selected = _selected_conflict()
            html_link = selected.get("htmlLink")
            if html_link:
                QDesktopServices.openUrl(QUrl(html_link))

        def _skip():
            choice["value"] = "skip"
            dialog.accept()

        def _add():
            choice["value"] = "add"
            dialog.accept()

        open_btn.clicked.connect(_open_selected)
        skip_btn.clicked.connect(_skip)
        add_btn.clicked.connect(_add)

        dialog.exec()
        return choice["value"]

    def _auto_add_high_confidence(self):
        if not self.auto_add_high_confidence:
            return

        # Only auto-add high-confidence selections
        selected = self._selected_events()
        if not selected:
            return

        # Filter to high confidence only
        high_conf = [e for e in selected if e.confidence >= self.auto_select_threshold]
        if not high_conf:
            return

        # Auto-add only high-confidence selections
        self._handle_add_to_calendar(auto_only=True, override_events=high_conf)

    def _handle_export_ics(self):
        selected = self._selected_events()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select at least one suggestion.")
            return

        if not self.calendar_service:
            QMessageBox.warning(self, "Calendar", "Calendar service not available.")
            return

        if not self.ics_output_dir:
            QMessageBox.warning(self, "ICS Export", "ICS output directory not configured.")
            return

        file_path, count = self.calendar_service.export_ics(selected, self.ics_output_dir)
        QMessageBox.information(self, "ICS Download", f"Exported {count} item(s) to:\n{file_path}")
