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
    def __init__(self, model_name: str = "qwen2.5:1.5b", base_url: str = "http://localhost:11434"):
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
            # Build the prompt that instructs the AI on what format to produce
            prompt = f"""Analyze the message and provide a Summary and a Task Classification.

Categories for Task Classification:
1. Smart Draft: Needs a thoughtful, composed reply (e.g., questions, discussions).
2. Auto Reply: Needs a simple acknowledgement (e.g., "Noted", "OK", "Thanks").
3. Simple Reply: Informational only, no specific action needed (e.g., "I'm leaving now").
4. File Attachment: Sender is explicitly requesting a file.

Rules:
1. Refer to the sender as "The sender". DO NOT use their real name ({sender}).
2. If it's a channel join message, classify as "Simple Reply".
3. Format the output EXACTLY as follows:

Summary: [1-2 sentence summary]

Task: [Category Name]
[Brief reason for classification]

Message: {message_text}"""

            payload = {
                "model":   self.model_name,
                "prompt":  prompt,
                "stream":  False,
                "options": {"temperature": 0.3, "top_p": 0.9, "max_tokens": 100}
            }
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.summary_timeout_seconds
            )

            if response.status_code == 200:
                result  = response.json()
                summary = result.get('response', '').strip()
                return summary if summary else "Unable to generate summary"
            else:
                error_body = (response.text or "").strip().replace("\n", " ")
                if len(error_body) > 240:
                    error_body = error_body[:240] + "..."
                self.error_occurred.emit(
                    f"Ollama summary request failed (HTTP {response.status_code}): {error_body}"
                )
                return None

        except requests.exceptions.Timeout:
            self.error_occurred.emit(
                f"Ollama summary request timed out after {self.summary_timeout_seconds}s"
            )
            return None
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("Cannot connect to Ollama. Is it running?")
            return None
        except Exception as e:
            self.error_occurred.emit(f"Error generating summary: {str(e)}")
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
                "options": {"temperature": temperature, "top_p": 0.9, "max_tokens": max_tokens},
            }
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=self.text_timeout_seconds
            )
            if response.status_code != 200:
                error_body = (response.text or "").strip().replace("\n", " ")
                if len(error_body) > 240:
                    error_body = error_body[:240] + "..."
                self.error_occurred.emit(
                    f"Ollama text request failed (HTTP {response.status_code}): {error_body}"
                )
                return None
            result = response.json()
            output = result.get("response", "").strip()
            return output if output else None

        except requests.exceptions.Timeout:
            self.error_occurred.emit(
                f"Ollama text request timed out after {self.text_timeout_seconds}s"
            )
            return None
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("Cannot connect to Ollama. Is it running?")
            return None
        except Exception as e:
            self.error_occurred.emit(f"Error generating text: {str(e)}")
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
        new_messages = [
            msg for msg in messages
            if (not msg.get('summary') or msg.get('summary') == '')
            and not any(m.get('id') == msg.get('id') for m in self.queue)
        ]
        if not new_messages:
            return
        self.queue.extend(new_messages)
        self.total_count += len(new_messages)
        print(f"Added {len(new_messages)} messages to summary queue. Total in queue: {len(self.queue)}")
        self.process_queue()

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
