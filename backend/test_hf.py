from pathlib import Path
from dotenv import load_dotenv
import os

from huggingface_hub import InferenceClient

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")

if not HF_TOKEN:
    raise ValueError("HF_TOKEN is missing from .env")

client = InferenceClient(
    api_key=HF_TOKEN,
    provider="auto"
)

response = client.chat.completions.create(
    model="Qwen/Qwen3-8B",
    messages=[
        {
            "role": "user",
            "content": "Explain RAG in one short sentence."
        }
    ],
)

print(response.choices[0].message.content)