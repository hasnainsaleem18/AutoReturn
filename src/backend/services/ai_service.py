# -------------------------
# AI SERVICE
# -------------------------
"""
Manages all AI text generation for AutoReturn.
Connects to the local Ollama model and handles:
- Email and Slack message summarization
- Reply draft generation
- Background thread management so the UI never freezes
"""

import requests
import asyncio
from typing import Optional
from PySide6.QtCore import QThread, Signal, QObject


DEFAULT_OLLAMA_MODEL = "qwen3-next:80b-cloud"
SUMMARY_INPUT_CHAR_LIMIT = 1200
SUMMARY_NUM_PREDICT = 70


# -------------------------
# OLLAMA SERVICE CLASS
# Main connection class between AutoReturn and the local Ollama AI model.
# All AI generation (summaries, drafts) must go through this class.
# -------------------------
class OllamaService(QObject):
    """Talks to the local Ollama AI server at http://localhost:11434."""

    summary_generated = Signal(str, str)   # Signals: message_id, summary text
    error_occurred    = Signal(str)         # Signal:  error message string

    # -------------------------
    # CONSTRUCTOR: STORE SERVER CONFIG
    # Saves the AI model name and server address for all future requests.
    # -------------------------
    def __init__(self, model_name: str = DEFAULT_OLLAMA_MODEL, base_url: str = "http://localhost:11434"):
        super().__init__()
        self.model_name = model_name
        self.base_url   = base_url
        self.api_url    = f"{base_url}/api/generate"   # Endpoint for text generation
        # Local models on CPU can exceed 60s on longer prompts.
        self.summary_timeout_seconds = 180
        self.text_timeout_seconds = 120

    # -------------------------
    # CHECK IF OLLAMA IS RUNNING
    # Pings the Ollama server and returns True if it responds with OK.
    # Called on app startup to warn the user if AI is not available.
    # -------------------------
    def check_connection(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False

    def check_model_available(self) -> bool:
        """Return True when the configured Ollama model exists locally."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if response.status_code != 200:
                return False
            payload = response.json()
            models = payload.get("models", [])
            names = {str(model.get("name", "")).strip() for model in models}
            return self.model_name in names
        except Exception:
            return False

    @staticmethod
    def _trim_summary_input(message_text: str) -> str:
        """Keep local CPU prompts bounded so summary generation completes."""
        text = (message_text or "").strip()
        if len(text) <= SUMMARY_INPUT_CHAR_LIMIT:
            return text

        head_size = int(SUMMARY_INPUT_CHAR_LIMIT * 0.7)
        tail_size = SUMMARY_INPUT_CHAR_LIMIT - head_size
        return (
            text[:head_size].rstrip()
            + "\n\n[...middle content omitted for speed...]\n\n"
            + text[-tail_size:].lstrip()
        )

    # -------------------------
    # ASYNC WRAPPER: GENERATE SUMMARY
    # Non-blocking version of generate_summary for use inside async agent code.
    # Runs the sync version in a background thread so the UI stays responsive.
    # -------------------------
    async def generate_summary_async(self, message_text: str, sender: str = "", subject: str = "") -> Optional[str]:
        return await asyncio.to_thread(self.generate_summary, message_text, sender, subject)

    # -------------------------
    # ASYNC WRAPPER: GENERATE TEXT
    # Non-blocking version of generate_text for draft/rewrite tasks.
    # Runs the sync version in a background thread so the UI stays responsive.
    # -------------------------
    async def generate_text_async(self, prompt: str, temperature: float = 0.55, max_tokens: int = 260) -> Optional[str]:
        return await asyncio.to_thread(self.generate_text, prompt, temperature, max_tokens)

    # -------------------------
    # GENERATE AI SUMMARY (SYNCHRONOUS)
    # Sends message text to Ollama and gets back a 1-2 sentence summary
    # plus a task classification (Smart Draft, Auto Reply, etc.).
    # Returns the AI response string, or None on failure.
    # -------------------------
    def generate_summary(self, message_text: str, sender: str = "", subject: str = "") -> Optional[str]:
        try:
            message_text = self._trim_summary_input(message_text)
            # Keep this prompt compact; local 7B CPU inference is prompt-length sensitive.
            prompt = f"""Summarize and classify this inbox message.
Return exactly two lines:
Summary: <25 words max, refer to the sender as "The sender">
Task: <Smart Draft | Auto Reply | Simple Reply | File Attachment>

Classify as File Attachment only when the sender asks for a file. Classify as Auto Reply only when a short acknowledgement is enough.

Sender: {sender}
Subject: {subject}
Message: {message_text}"""

            payload = {
                "model":   self.model_name,
                "prompt":  prompt,
                "stream":  False,
                "options": {
                    "temperature": 0.2,
                    "top_p": 0.9,
                    "num_predict": 200,
                    "num_ctx": 4096,
                },
            }
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.summary_timeout_seconds
            )

            if response.status_code == 200:
                result  = response.json()
                summary = result.get('response', '').strip()
                print(f"[OllamaService] Summary generated OK ({len(summary)} chars)")
                return summary if summary else "Unable to generate summary"
            else:
                error_body = (getattr(response, "text", "") or "").strip().replace("\n", " ")
                if len(error_body) > 240:
                    error_body = error_body[:240] + "..."
                msg = f"Ollama summary request failed (HTTP {response.status_code}): {error_body}"
                print(f"[OllamaService] ERROR: {msg}")
                self.error_occurred.emit(msg)
                return None

        except requests.exceptions.Timeout:
            msg = f"Ollama summary timed out after {self.summary_timeout_seconds}s — model may still be loading"
            print(f"[OllamaService] TIMEOUT: {msg}")
            self.error_occurred.emit(msg)
            return None
        except requests.exceptions.ConnectionError:
            msg = "Cannot connect to Ollama at localhost:11434 — is 'ollama serve' running?"
            print(f"[OllamaService] CONNECTION ERROR: {msg}")
            self.error_occurred.emit(msg)
            return None
        except Exception as e:
            msg = f"Error generating summary: {str(e)}"
            print(f"[OllamaService] EXCEPTION: {msg}")
            self.error_occurred.emit(msg)
            return None

    # -------------------------
    # GENERATE FREE-FORM TEXT (SYNCHRONOUS)
    # Sends any custom prompt to Ollama and returns the raw AI text response.
    # Used by the Tone Engine and Draft Manager for reply generation and rewriting.
    # -------------------------
    def generate_text(self, prompt: str, temperature: float = 0.55, max_tokens: int = 260) -> Optional[str]:
        try:
            payload = {
                "model":   self.model_name,
                "prompt":  prompt,
                "stream":  False,
                "options": {
                    "temperature": temperature,
                    "top_p": 0.9,
                    "num_predict": max_tokens,
                    "num_ctx": 2048,
                },
            }
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.text_timeout_seconds
            )
            if response.status_code != 200:
                error_body = (getattr(response, "text", "") or "").strip().replace("\n", " ")
                if len(error_body) > 240:
                    error_body = error_body[:240] + "..."
                msg = f"Ollama text request failed (HTTP {response.status_code}): {error_body}"
                print(f"[OllamaService] ERROR: {msg}")
                self.error_occurred.emit(msg)
                return None
            result = response.json()
            output = result.get("response", "").strip()
            print(f"[OllamaService] Text generated OK ({len(output)} chars)")
            return output if output else None

        except requests.exceptions.Timeout:
            msg = f"Ollama text timed out after {self.text_timeout_seconds}s"
            print(f"[OllamaService] TIMEOUT: {msg}")
            self.error_occurred.emit(msg)
            return None
        except requests.exceptions.ConnectionError:
            msg = "Cannot connect to Ollama at localhost:11434"
            print(f"[OllamaService] CONNECTION ERROR: {msg}")
            self.error_occurred.emit(msg)
            return None
        except Exception as e:
            msg = f"Error generating text: {str(e)}"
            print(f"[OllamaService] EXCEPTION: {msg}")
            self.error_occurred.emit(msg)
            return None


# -------------------------
# SUMMARY GENERATOR THREAD
# A QThread that generates one AI summary in the background.
# By running in a separate thread, the main window never freezes.
# -------------------------
class SummaryGeneratorThread(QThread):
    """Generates a single summary in a background thread."""

    summary_ready  = Signal(str, str)   # Emitted on success: message_id, summary
    error_occurred = Signal(str, str)   # Emitted on failure: message_id, error

    # -------------------------
    # CONSTRUCTOR: STORE MESSAGE DATA
    # Saves all data needed to generate the summary when the thread runs.
    # -------------------------
    def __init__(self, ollama_service: OllamaService, message_id: str,
                 message_text: str, sender: str = "", subject: str = ""):
        super().__init__()
        self.ollama_service = ollama_service
        self.message_id     = message_id
        self.message_text   = message_text
        self.sender         = sender
        self.subject        = subject

    # -------------------------
    # RUN: EXECUTE SUMMARY IN BACKGROUND
    # Called automatically when thread.start() is invoked.
    # Fires summary_ready signal on success, error_occurred signal on failure.
    # -------------------------
    def run(self):
        try:
            summary = self.ollama_service.generate_summary(
                self.message_text, self.sender, self.subject
            )
            if summary:
                self.summary_ready.emit(self.message_id, summary)
            else:
                self.error_occurred.emit(self.message_id, "Failed to generate summary")
        except Exception as e:
            self.error_occurred.emit(self.message_id, str(e))


# -------------------------
# QUEUE SUMMARY GENERATOR
# Manages a waiting queue of messages that need AI summaries.
# Runs up to max_concurrent summaries at once and processes the rest
# one-by-one so Ollama is never overwhelmed.
# -------------------------
class QueueSummaryGenerator(QObject):
    """Queue-based manager that generates summaries without crashing Ollama."""

    summary_generated = Signal(str, str)   # message_id, summary text
    error_occurred    = Signal(str, str)   # message_id, error text
    batch_complete    = Signal(int)         # total count when full queue is done
    progress_update   = Signal(int, int)    # current completed, total queued

    # -------------------------
    # CONSTRUCTOR: INITIALIZE QUEUE STATE
    # Sets up an empty queue and configures the concurrency limit.
    # -------------------------
    def __init__(self, ollama_service: OllamaService, max_concurrent: int = 5):
        super().__init__()
        self.ollama_service  = ollama_service
        self.max_concurrent  = max_concurrent   # Max parallel summary threads at one time
        self.queue           = []
        self.active_threads  = []
        self.completed_count = 0
        self.total_count     = 0
        self.is_processing   = False

    # -------------------------
    # ADD MESSAGES TO QUEUE
    # Accepts a list of messages and adds only unsummarized, non-duplicate ones.
    # Immediately starts processing after adding.
    # -------------------------
    def add_to_queue(self, messages: list):
        if not self.is_processing and not self.active_threads and not self.queue:
            self.completed_count = 0
            self.total_count = 0

        FAILED_SUMMARIES = {"unable to generate summary", "failed to generate summary", "summary unavailable", "no content to summarize"}

        new_messages = [
            msg for msg in messages
            if (
                not msg.get('summary')
                or msg.get('summary') == ''
                or str(msg.get('summary', '')).lower().strip() in FAILED_SUMMARIES
            )
            and not any(m.get('id') == msg.get('id') for m in self.queue)
            and str(
                msg.get('full_content', msg.get('content_preview', msg.get('preview', '')))
                or ""
            ).strip()
        ]
        if not new_messages:
            return 0
        self.queue.extend(new_messages)
        self.total_count += len(new_messages)
        print(f"Added {len(new_messages)} messages to summary queue. Total in queue: {len(self.queue)}")
        self.process_queue()
        return len(new_messages)

    # -------------------------
    # PROCESS THE QUEUE
    # The main loop that starts new summary threads whenever a slot is free.
    # Automatically called every time a thread finishes to pick up the next item.
    # -------------------------
    def process_queue(self):
        if not self.queue:
            if not self.active_threads:
                self.is_processing = False
                self.batch_complete.emit(self.completed_count)
            return

        self.is_processing = True

        # Spin up threads until we hit the concurrency limit
        while len(self.active_threads) < self.max_concurrent and self.queue:
            msg = self.queue.pop(0)
            thread = SummaryGeneratorThread(
                self.ollama_service,
                msg.get('id', ''),
                msg.get('full_content', msg.get('content_preview', msg.get('preview', ''))),
                msg.get('sender', ''),
                msg.get('subject', '')
            )
            thread.summary_ready.connect(self._on_summary_ready)
            thread.error_occurred.connect(self._on_error)
            thread.finished.connect(lambda t=thread: self._on_thread_finished(t))
            self.active_threads.append(thread)
            thread.start()

    # -------------------------
    # HANDLE SUCCESSFUL SUMMARY
    # Called when a thread finishes and produced a valid summary.
    # Emits signal so the UI table row can be updated with the new summary.
    # -------------------------
    def _on_summary_ready(self, message_id: str, summary: str):
        self.summary_generated.emit(message_id, summary)
        self.completed_count += 1
        self.progress_update.emit(self.completed_count, self.total_count)

    # -------------------------
    # HANDLE SUMMARY ERROR
    # Called when a thread fails (e.g., Ollama offline or timeout).
    # Still increments progress count so the queue continues moving.
    # -------------------------
    def _on_error(self, message_id: str, error: str):
        print(f"Error generating summary for {message_id}: {error}")
        self.error_occurred.emit(message_id, error)
        self.completed_count += 1
        self.progress_update.emit(self.completed_count, self.total_count)

    # -------------------------
    # HANDLE THREAD FINISHED
    # Called when any thread finishes (success or error).
    # Removes it from active list and triggers the next item in the queue.
    # -------------------------
    def _on_thread_finished(self, thread):
        if thread in self.active_threads:
            self.active_threads.remove(thread)
        self.process_queue()   # Pick up the next waiting message

    # -------------------------
    # STOP ALL THREADS AND CLEAR QUEUE
    # Called when the application is closing.
    # Prevents threads from running in the background after the window closes.
    # -------------------------
    def stop_all(self):
        self.queue.clear()
        for thread in self.active_threads:
            thread.quit()
            thread.wait()
        self.active_threads.clear()
        self.is_processing = False
