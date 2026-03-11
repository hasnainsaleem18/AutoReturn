import requests

payload = {
    "model": "glm-5:cloud",
    "prompt": "You are an email assistant. Analyze the message and provide ONLY the final output format. Do not include your reasoning steps in the final output.\n\nSummary: [1-2 sentence summary]\n\nTask: [Category Name]\n[Brief reason for classification]\n\nMessage: Hello, I need the quarterly report by Friday.",
    "stream": False,
    "keep_alive": "0m",
    "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 100}
}

try:
    res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
    result = res.json()
    
    raw_text = result.get('response', '').strip()
    if not raw_text:
        raw_text = result.get('thinking', '').strip()
        
    if "Summary:" in raw_text:
        summary = raw_text.split("Summary:", 1)[1].strip()
    else:
        summary = raw_text.strip()
        
    print("----- EXTRACTED -----")
    if "Task:" in summary:
        summary = summary.split("Task:", 1)[0].strip()
    print(summary)
except Exception as e:
    print(f"Error: {e}")
