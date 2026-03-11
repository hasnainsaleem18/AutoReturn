import requests
import json

payload = {
    "model": "kimi-k2.5:cloud",
    "prompt": "You are an email assistant. Analyze the message and provide a Summary and a Task Classification.\n\nCategories for Task Classification:\n1. Smart Draft\n2. Auto Reply\n3. Simple Reply\n4. File Attachment\n\nReturn EXACTLY this JSON structure and nothing else:\n{\n  \"summary\": \"[1-2 sentence summary]\",\n  \"task\": \"[Category Name: Brief reason]\"\n}\n\nMessage: Hello, I need the quarterly report by Friday.",
    "stream": False,
    "keep_alive": "0m",
    "format": "json",
    "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 100}
}

try:
    res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
    result = res.json()
    
    raw_text = result.get('response', '').strip()
    print("--- RAW API OUTPUT ---")
    print(raw_text)
    
    # Try parsing
    try:
        data = json.loads(raw_text)
        print("\n--- EXTRACTED JSON ---")
        print(f"Summary: {data.get('summary')}")
        print(f"Task: {data.get('task')}")
    except json.JSONDecodeError:
        print("\n--- Failed to parse JSON! ---")
    
except Exception as e:
    print(f"Error: {e}")
