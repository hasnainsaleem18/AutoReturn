# -------------------------
# PLAIN REPLY REVIEW DIALOG
# -------------------------
"""
Pre-send review dialog for plain reply flow.
"""

# -------------------------
# IMPORTS
# -------------------------
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
)


# -------------------------
# PLAIN REPLY REVIEW DIALOG CLASS
# Final confirmation modal shown before sending plain replies.
# Gives user three outcomes: edit, cancel, or send.
# -------------------------
class PlainReplyReviewDialog(QDialog):
    """Confirm plain reply content and attachments before sending."""

    # -------------------------
    # INIT
    # Builds a read-only review screen with message metadata, body,
    # attachments, optional note, and final action buttons.
    # -------------------------
    def __init__(
        self,
        source: str,
        recipient: str,
        subject: str,
        message_text: str,
        attachments: list,
        attachment_note: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.decision = "cancel"

        self.setWindowTitle("Review Plain Reply")
        self.resize(760, 560)
        self.setMinimumSize(660, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(10)

        title = QLabel("Review Before Sending")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #003135;")
        layout.addWidget(title)

        meta = QLabel(f"Source: {source.upper()}   |   Recipient: {recipient}\nSubject: {subject or '(No Subject)'}")
        meta.setWordWrap(True)
        meta.setStyleSheet("font-size: 13px; color: #024950;")
        layout.addWidget(meta)

        body_label = QLabel("Message to Send")
        body_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #003135;")
        layout.addWidget(body_label)

        body = QTextEdit()
        body.setReadOnly(True)
        body.setMinimumHeight(190)
        body.setPlainText(message_text or "(No message body)")
        layout.addWidget(body)

        attach_label = QLabel("Attachments")
        attach_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #003135;")
        layout.addWidget(attach_label)

        attach_box = QTextEdit()
        attach_box.setReadOnly(True)
        attach_box.setMinimumHeight(90)
        if attachments:
            attach_box.setPlainText("\n".join([f"• {path}" for path in attachments]))
        else:
            attach_box.setPlainText("No attachments")
        layout.addWidget(attach_box)

        if attachment_note:
            note = QTextEdit()
            note.setReadOnly(True)
            note.setMinimumHeight(84)
            note.setPlainText(f"Attachment note:\n{attachment_note}")
            note.setStyleSheet(
                """
                background-color: #FFF8EE;
                border: 1px solid #F2D3A2;
                border-left: 4px solid #F59E0B;
                border-radius: 8px;
                color: #5C3B00;
                font-size: 13px;
                font-weight: 600;
                """
            )
            layout.addWidget(note)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        edit_btn = QPushButton("Edit in Composer")
        edit_btn.setObjectName("btnSecondary")
        edit_btn.clicked.connect(self._on_edit)
        btn_row.addWidget(edit_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("btnSecondary")
        cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(cancel_btn)

        send_btn = QPushButton("Send Now")
        send_btn.setObjectName("btnPrimary")
        send_btn.clicked.connect(self._on_send)
        btn_row.addWidget(send_btn)

        layout.addLayout(btn_row)

    # -------------------------
    # EDIT ACTION
    # User wants to return to composer and modify message before send.
    # -------------------------
    def _on_edit(self):
        self.decision = "edit"
        self.reject()

    # -------------------------
    # CANCEL ACTION
    # User aborts send operation from review dialog.
    # -------------------------
    def _on_cancel(self):
        self.decision = "cancel"
        self.reject()

    # -------------------------
    # SEND ACTION
    # User confirms message and attachments are ready to be sent.
    # -------------------------
    def _on_send(self):
        self.decision = "send"
        self.accept()
