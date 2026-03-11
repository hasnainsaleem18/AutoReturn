#!/usr/bin/env python3
# -------------------------
# OLLAMA INTEGRATION TEST
# -------------------------
"""
Test script to verify Ollama integration.
"""

# -------------------------
# IMPORTS
# -------------------------
import sys
import os

# Add project root and src to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from src.backend.services.ai_service import OllamaService


# -------------------------
# TEST OLLAMA SERVICE
# Verifies:
# 1) local server connectivity
# 2) summary generation response path
# -------------------------
def test_ollama():
    print("Testing Ollama connection...")
    
    ollama = OllamaService(model_name="qwen2.5:1.5b")
    
    # Test connection
    if not ollama.check_connection():
        print("Ollama is not running or not accessible")
        return False
    
    print("Ollama is running")
    
    # Test summary generation
    print("\nTesting summary generation...")
    test_message = """
    Hey team, just wanted to remind everyone about the important meeting tomorrow at 2 PM.
    We'll be discussing the Q4 roadmap and need everyone's input on the new features.
    Please review the documents I sent earlier and come prepared with your thoughts.
    This is urgent as we need to finalize everything by end of week.
    """
    
    summary = ollama.generate_summary(
        message_text=test_message,
        sender="John Doe",
        subject="Q4 Meeting Reminder"
    )
    
    if summary:
        print(f"Summary generated successfully:")
        print(f"   {summary}")
        return True
    else:
        print("Failed to generate summary")
        return False


# -------------------------
# MAIN ENTRY
# Returns process exit code based on test success/failure.
# -------------------------
if __name__ == "__main__":
    success = test_ollama()
    sys.exit(0 if success else 1)
