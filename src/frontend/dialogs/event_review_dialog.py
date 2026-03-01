# -------------------------
# EVENT REVIEW DIALOG
# -------------------------
"""
Dialog for reviewing extracted events/tasks and adding them to calendar.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt

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

        self.setWindowTitle("Review Extracted Events")
        self.setMinimumSize(760, 420)

        self._build_ui()
        self._auto_add_high_confidence()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Review extracted events/tasks before adding to Calendar")
        title.setStyleSheet("font-size: 16px; font-weight: 600; color: #003135;")
        layout.addWidget(title)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 12px; color: #024950;")
        layout.addWidget(self.status_label)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Add", "Title", "Start", "End", "Type", "Confidence"
        ])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setRowCount(len(self.events))
        self.table.verticalHeader().setVisible(False)

        for row, ev in enumerate(self.events):
            confidence = float(ev.get("confidence", 0.0))

            checkbox = QCheckBox()
            checkbox.setChecked(confidence >= self.auto_select_threshold)
            self.table.setCellWidget(row, 0, checkbox)

            self.table.setItem(row, 1, QTableWidgetItem(ev.get("title", "")))
            self.table.setItem(row, 2, QTableWidgetItem(self._fmt_dt(ev.get("start_dt"))))
            self.table.setItem(row, 3, QTableWidgetItem(self._fmt_dt(ev.get("end_dt"))))
            self.table.setItem(row, 4, QTableWidgetItem(ev.get("item_type", "event")))
            self.table.setItem(row, 5, QTableWidgetItem(f"{confidence:.2f}"))

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(1, 260)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        add_btn = QPushButton("Add to Google Calendar")
        add_btn.clicked.connect(self._handle_add_to_calendar)

        export_btn = QPushButton("Export ICS")
        export_btn.clicked.connect(self._handle_export_ics)

        close_btn = QPushButton("Close")
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

    def _selected_events(self) -> List[EventCandidate]:
        selected = []
        for row, ev in enumerate(self.events):
            widget = self.table.cellWidget(row, 0)
            if isinstance(widget, QCheckBox) and widget.isChecked():
                try:
                    selected.append(EventCandidate(**ev))
                except Exception:
                    continue
        return selected

    def _handle_add_to_calendar(self, auto_only: bool = False, override_events: List[EventCandidate] = None):
        selected = override_events if override_events is not None else self._selected_events()
        if not selected:
            if not auto_only:
                QMessageBox.information(self, "No Events", "No events selected.")
            return

        if not self.calendar_service:
            if not auto_only:
                QMessageBox.warning(self, "Calendar", "Calendar service not available.")
            return

        ok, msg = self.calendar_service.connect(allow_flow=True)
        if not ok:
            if not auto_only:
                QMessageBox.warning(self, "Calendar", msg)
            return

        created, errors = self.calendar_service.create_events(selected)
        if auto_only:
            if created > 0:
                self.status_label.setText(f"Auto-added {created} high-confidence events.")
            if errors:
                self.status_label.setText(f"Auto-add had errors: {errors}")
            return

        if errors:
            QMessageBox.warning(self, "Calendar", f"Created {created} events. Errors: {errors}")
        else:
            QMessageBox.information(self, "Calendar", f"Created {created} events.")

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
            QMessageBox.information(self, "No Events", "No events selected.")
            return

        if not self.calendar_service:
            QMessageBox.warning(self, "Calendar", "Calendar service not available.")
            return

        if not self.ics_output_dir:
            QMessageBox.warning(self, "ICS Export", "ICS output directory not configured.")
            return

        file_path, count = self.calendar_service.export_ics(selected, self.ics_output_dir)
        QMessageBox.information(self, "ICS Export", f"Exported {count} events to:\n{file_path}")
