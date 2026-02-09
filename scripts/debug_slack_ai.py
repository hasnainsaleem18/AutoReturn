#!/usr/bin/env python3
"""
Debug script to test Slack integration with AI summary generation
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

def test_slack_with_ai():
    print("=" * 70)
    print("SLACK + AI SUMMARY INTEGRATION TEST")
    print("=" * 70)
    
    # Your Slack token
    # Your Slack token
    # slack_token = "YOUR_TOKEN_HERE"
    import keyring
    slack_token = keyring.get_password("autoreturn", "slack_token")
    if not slack_token:
        print("   ❌ No Slack token found in keyring!")
        return False
    
    print("\n1. Testing Ollama connection...")
    ollama = OllamaService(model_name="kimi-k2.5:cloud")
    
    if not ollama.check_connection():
        print("   ❌ Ollama is NOT running!")
        print("\n   Please start Ollama:")
        print("   $ ollama serve")
        return False
    
    print("   ✅ Ollama is running")
    
    print("\n2. Connecting to Slack...")
    slack = SlackService()
    
    if not slack.connect(slack_token):
        print("   ❌ Failed to connect to Slack")
        return False
    
    print(f"   ✅ Connected to Slack as {slack.my_user_name}")
    print(f"   Workspace: {slack.workspace_name}")
    
    print("\n3. Fetching recent messages...")
    messages = slack.fetch_all_messages(limit=5)
    
    if not messages:
        print("   ⚠️  No messages found")
        print("\n   Try sending a message in Slack and run this script again")
        return True
    
    print(f"   ✅ Found {len(messages)} messages")
    
    print("\n4. Testing AI summary generation...")
    print("=" * 70)
    
    for i, msg in enumerate(messages, 1):
        print(f"\nMessage {i}/{len(messages)}")
        print("-" * 70)
        print(f"From: {msg.get('sender', 'Unknown')}")
        print(f"Channel: {msg.get('channel_name', 'N/A')}")
        print(f"Content: {msg.get('full_content', '')[:100]}...")
        print(f"Current Summary: {msg.get('summary', 'NONE')}")
        
        print("\nGenerating AI summary...", end=" ", flush=True)
        
        summary = ollama.generate_summary(
            message_text=msg.get('full_content', msg.get('preview', '')),
            sender=msg.get('sender', ''),
            subject=msg.get('subject', msg.get('content_preview', ''))
        )
        
        if summary:
            print("✅")
            print(f"AI Summary: {summary}")
            
            # Check if it's different from current summary
            if msg.get('summary') != summary:
                print(f"⚠️  Summary is DIFFERENT from what's in the message data!")
                print(f"   Message data summary: {msg.get('summary', 'NONE')}")
        else:
            print("❌ FAILED")
        
        print("-" * 70)
    
    print("\n" + "=" * 70)
    print("DIAGNOSIS:")
    print("=" * 70)
    
    # Check if messages have summaries
    messages_with_summaries = [m for m in messages if m.get('summary')]
    messages_without_summaries = [m for m in messages if not m.get('summary')]
    
    print(f"\nMessages with summaries: {len(messages_with_summaries)}/{len(messages)}")
    print(f"Messages without summaries: {len(messages_without_summaries)}/{len(messages)}")
    
    if messages_without_summaries:
        print("\n⚠️  ISSUE FOUND: Some messages don't have summaries!")
        print("   This means the automatic summary generation might not be working.")
        print("\n   Possible causes:")
        print("   1. Ollama was not running when messages arrived")
        print("   2. Summary generation failed silently")
        print("   3. Messages arrived before AI service was initialized")
        print("\n   Solution:")
        print("   - Click '🤖 Generate Summaries' button in the app")
        print("   - Or restart the app with Ollama already running")
    else:
        print("\n✅ All messages have summaries!")
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    
    return True

if __name__ == "__main__":
    try:
        success = test_slack_with_ai()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
