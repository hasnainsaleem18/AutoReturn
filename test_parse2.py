import requests

payload = {
    "model": "glm-5:cloud",
    "prompt": "You are an email assistant. Analyze the message and provide a Summary and a Task Classification.\n\nSummary: [1-2 sentence summary]\n\nTask: [Category Name]\n[Brief reason for classification]\n\nMessage: Hello, I need the quarterly report by Friday.",
    "stream": False,
    "keep_alive": "0m",
    "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 100}
}
res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
result = res.json()
print("---- RAW RESPONSE ----")
print(result.get('response', ''))
print("---- RAW THINKING ----")
print(result.get('thinking', ''))
