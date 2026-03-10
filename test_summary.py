import requests

payload = {
    "model": "glm-5:cloud",
    "prompt": "Analyze this message.\n\nMessage: Hello, I need the quarterly report by Friday.",
    "stream": False,
    "keep_alive": "0m",
    "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 100}
}

try:
    print("Testing Ollama API...")
    res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
    print(f"Status Code: {res.status_code}")
    print(f"Response: {res.text[:200]}")
except Exception as e:
    print(f"Error: {e}")
