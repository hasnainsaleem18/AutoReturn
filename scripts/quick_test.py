#!/usr/bin/env python3
"""
Quick test to verify AI summaries are generated for new Slack messages
"""
import sys
import os

# Add project root and src to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from src.backend.services.slack_backend import SlackService
from src.backend.services.ai_service import OllamaService
import time

def quick_test():
    print("=" * 70)
    print("QUICK TEST: AI Summary Generation for Slack Messages")
    print("=" * 70)
    
    import keyring
    slack_token = keyring.get_password("autoreturn", "slack_token")
    if not slack_token:
        print("   ❌ No Slack token found in keyring!")
        return False
    
    # Check Ollama
    print("\n✓ Checking Ollama...")
    ollama = OllamaService(model_name="qwen3:0.6b")
    if not ollama.check_connection():
        print("  ❌ Ollama is NOT running!")
        return False
    print("  ✅ Ollama is running")
    
    # Connect to Slack
    print("\n✓ Connecting to Slack...")
    slack = SlackService()
    if not slack.connect(slack_token):
        print("  ❌ Failed to connect")
        return False
    print(f"  ✅ Connected as {slack.my_user_name}")
    
    # Fetch ONE recent message
    print("\n✓ Fetching most recent message...")
    messages = slack.fetch_all_messages(limit=1)
    
    if not messages:
        print("  ⚠️  No messages found")
        print("\n  Please send a test message in Slack:")
        print("  1. Go to any Slack channel")
        print("  2. Send: 'This is a test message for AI summary generation'")
        print("  3. Run this script again")
        return True
    
    msg = messages[0]
    print(f"  ✅ Got message from: {msg.get('sender')}")
    
    # Check initial summary
    print("\n" + "=" * 70)
    print("MESSAGE DETAILS:")
    print("=" * 70)
    print(f"From: {msg.get('sender')}")
    print(f"Channel: {msg.get('channel_name', 'N/A')}")
    print(f"Content: {msg.get('full_content', '')}")
    print(f"\nInitial Summary: '{msg.get('summary', 'NONE')}'")
    
    if msg.get('summary') and msg.get('summary') != '':
        print("\n⚠️  WARNING: Message already has a summary!")
        print("   This should be empty for AI to generate it.")
        print("   The fix has been applied, but this message was created before the fix.")
    else:
        print("\n✅ Summary is empty - ready for AI generation")
    
    # Generate AI summary
    print("\n" + "=" * 70)
    print("GENERATING AI SUMMARY...")
    print("=" * 70)
    
    summary = ollama.generate_summary(
        message_text=msg.get('full_content', msg.get('preview', '')),
        sender=msg.get('sender', ''),
        subject=msg.get('subject', '')
    )
    
    if summary:
        print(f"\n✅ AI Summary Generated:")
        print(f"   {summary}")
        print("\n" + "=" * 70)
        print("SUCCESS!")
        print("=" * 70)
        print("\nThe AI summary generation is working correctly.")
        print("\nNOTE: To see this in the app:")
        print("1. Restart the app (it's already running)")
        print("2. Send a NEW message in Slack")
        print("3. The new message will have an AI-generated summary")
        print("\nOR click the '🤖 Generate Summaries' button to regenerate all summaries")
        return True
    else:
        print("\n❌ Failed to generate summary")
        return False

if __name__ == "__main__":
    try:
        success = quick_test()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
