import requests
import os
from dotenv import load_dotenv

load_dotenv()

HF_API_KEY = os.getenv("HF_API_KEY")
print(f"Key starts with: {HF_API_KEY[:10] if HF_API_KEY else 'NOT FOUND'}")

# تيست بسيط
response = requests.get(
    "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
    headers={"Authorization": f"Bearer {HF_API_KEY}"}
)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:200]}")