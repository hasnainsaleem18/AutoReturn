import requests
import re

payload = {
    "model": "kimi-k2.5:cloud",
    "prompt": "You are an email assistant. Analyze the message and provide a Summary and a Task Classification.\n\nCategories for Task Classification:\n1. Smart Draft\n2. Auto Reply\n3. Simple Reply\n4. File Attachment\n\nRules:\n1. Provide your final output wrapped EXACTLY in XML tags as follows:\n<summary>[1-2 sentence summary]</summary>\n<task>[Category Name]</task>\n\nMessage: Hello, I need the quarterly report by Friday.",
    "stream": False,
    "keep_alive": "0m",
    "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 100}
}
res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=30)
result = res.json()

text = result.get('response', '') or result.get('thinking', '')
print("--- RAW API OUTPUT ---")
print(text)

summary_match = re.search(r'<summary>(.*?)</summary>', text, re.DOTALL | re.IGNORECASE)
if summary_match:
    print(f"\n--- EXTRACTED ---")
    print(summary_match.group(1).strip())
else:
    print("\n--- Failed to extract tags! ---")
