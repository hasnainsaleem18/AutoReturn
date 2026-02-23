# -------------------------
# AI SERVICE
# -------------------------
"""
Module for AI-related functionality including:
- Text summarization using Ollama
- Background processing of message queues
- Thread-safe summary generation
"""

# -------------------------
# IMPORTS
# -------------------------
import requests
import json
import asyncio
from typing import Optional
from PySide6.QtCore import QThread, Signal, QObject


# -------------------------
# OLLAMA SERVICE
# -------------------------
class OllamaService(QObject):
    """Service for interacting with Ollama API"""
    
    summary_generated = Signal(str, str)  # message_id, summary
    error_occurred = Signal(str)
    
    def __init__(self, model_name: str = "kimi-k2.5:cloud", base_url: str = "http://localhost:11434"):
        super().__init__()
        self.model_name = model_name
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
    
    def check_connection(self) -> bool:
        """Check if Ollama is running and accessible"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    async def generate_summary_async(self, message_text: str, sender: str = "", subject: str = "") -> Optional[str]:
        """Async version of generate_summary for use by agents."""
        return await asyncio.to_thread(self.generate_summary, message_text, sender, subject)
    
    def generate_summary(self, message_text: str, sender: str = "", subject: str = "") -> Optional[str]:
        """Generate a summary of the message using Ollama"""
        try:
            # Create a focused prompt for summarization and task extraction
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
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "max_tokens": 100
                }
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=60  # Increased timeout for concurrent requests
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get('response', '').strip()
                return summary if summary else "Unable to generate summary"
            else:
                return None
                
        except requests.exceptions.Timeout:
            self.error_occurred.emit("Ollama request timed out")
            return None
        except requests.exceptions.ConnectionError:
            self.error_occurred.emit("Cannot connect to Ollama. Is it running?")
            return None
        except Exception as e:
            self.error_occurred.emit(f"Error generating summary: {str(e)}")
            return None



# -------------------------
# SUMMARY GENERATOR THREAD
# -------------------------
class SummaryGeneratorThread(QThread):
    """Background thread for generating summaries without blocking UI"""
    
    summary_ready = Signal(str, str)  # message_id, summary
    error_occurred = Signal(str, str)  # message_id, error
    
    def __init__(self, ollama_service: OllamaService, message_id: str, 
                 message_text: str, sender: str = "", subject: str = ""):
        super().__init__()
        self.ollama_service = ollama_service
        self.message_id = message_id
        self.message_text = message_text
        self.sender = sender
        self.subject = subject
    
    def run(self):
        """Generate summary in background"""
        try:
            summary = self.ollama_service.generate_summary(
                self.message_text,
                self.sender,
                self.subject
            )
            
            if summary:
                self.summary_ready.emit(self.message_id, summary)
            else:
                self.error_occurred.emit(self.message_id, "Failed to generate summary")
                
        except Exception as e:
            self.error_occurred.emit(self.message_id, str(e))


# -------------------------
# QUEUE SUMMARY GENERATOR
# -------------------------
class QueueSummaryGenerator(QObject):
    """Manages queue-based generation of summaries to avoid overwhelming Ollama"""
    
    summary_generated = Signal(str, str)  # message_id, summary
    batch_complete = Signal(int)  # total summaries generated
    progress_update = Signal(int, int)  # current, total
    
    def __init__(self, ollama_service: OllamaService, max_concurrent: int = 2):
        super().__init__()
        self.ollama_service = ollama_service
        self.max_concurrent = max_concurrent
        self.queue = []
        self.active_threads = []
        self.completed_count = 0
        self.total_count = 0
        self.is_processing = False
    
    def add_to_queue(self, messages: list):
        """Add messages to the processing queue"""
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
    
    def process_queue(self):
        """Process messages in the queue up to max_concurrent"""
        if not self.queue:
            if not self.active_threads:
                self.is_processing = False
                self.batch_complete.emit(self.completed_count)
            return
        
        self.is_processing = True
        
        # Start threads until we reach max_concurrent or queue is empty
        while len(self.active_threads) < self.max_concurrent and self.queue:
            msg = self.queue.pop(0)
            
            thread = SummaryGeneratorThread(
                self.ollama_service,
                msg.get('id', ''),
                msg.get('full_content', msg.get('preview', '')),
                msg.get('sender', ''),
                msg.get('subject', '')
            )
            
            thread.summary_ready.connect(self._on_summary_ready)
            thread.error_occurred.connect(self._on_error)
            thread.finished.connect(lambda t=thread: self._on_thread_finished(t))
            
            self.active_threads.append(thread)
            thread.start()
    
    def _on_summary_ready(self, message_id: str, summary: str):
        """Handle summary generation completion"""
        self.summary_generated.emit(message_id, summary)
        self.completed_count += 1
        self.progress_update.emit(self.completed_count, self.total_count)
    
    def _on_error(self, message_id: str, error: str):
        """Handle summary generation error"""
        print(f"Error generating summary for {message_id}: {error}")
        self.completed_count += 1
        self.progress_update.emit(self.completed_count, self.total_count)
    
    def _on_thread_finished(self, thread):
        """Clean up finished thread and process next item"""
        if thread in self.active_threads:
            self.active_threads.remove(thread)
        
        # Process next item in queue
        self.process_queue()
    
    def stop_all(self):
        """Stop all active threads and clear queue"""
        self.queue.clear()
        for thread in self.active_threads:
            thread.quit()
            thread.wait()
        self.active_threads.clear()
        self.is_processing = False
