import os
import requests
from dotenv import load_dotenv

load_dotenv()


def generate_answer(question: str, context: str) -> str:

    prompt = f"""
    You are a document question-answering assistant.

    Answer the user's question using ONLY the information
    provided in the context.

    If the answer cannot be found in the context, say:

    "I couldn't find the answer in the provided documents."

    Do not make up information.

    Context:
    {context}

    Question:
    {question}

    Answer:
    """

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured")

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model": "nvidia/nemotron-3-ultra-550b-a55b:free",
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        },
        timeout=120,
    )

    response.raise_for_status()

    data = response.json()

    return data["choices"][0]["message"]["content"]
