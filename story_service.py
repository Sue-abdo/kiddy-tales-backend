from groq import Groq
import os
import json
from dotenv import load_dotenv

load_dotenv()

client = None

def get_groq_client():
    global client
    if client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY environment variable is required. "
                "Set it in your environment or in a .env file."
            )
        client = Groq(api_key=api_key)
    return client


def correct_words(words: str) -> dict: 
    """
    Check and correct spelling mistakes
    Returns: corrected words + was_corrected flag
    """
    prompt = f"""
You are a spelling checker for children aged 6-11.

The child wrote: "{words}"

Tasks:
1. Check if there are any spelling mistakes
2. If yes, correct them
3. Return the corrected version

Return ONLY this JSON, no extra text:
{{
  "original": "{words}",
  "corrected": "the corrected words here",
  "was_corrected": true or false,
  "corrections": [
    {{"wrong": "wrong word", "right": "correct word"}}
  ]
}}

If no mistakes, was_corrected = false and corrected = original.
"""

    client = get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=200
    )

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    return json.loads(text.strip())


def generate_story(words: str) -> dict:
    """
    Takes one word or multiple words from the child
    Returns: story + image_prompt (no questions anymore)
    """
    prompt = f"""
You are a friendly English teacher for children aged 6-11.

The child gave you these words: "{words}"

Please generate:
1. A SHORT simple story (5-10 sentences) that uses ALL the words the child provided.
   - Use simple English words
   - Make it fun and engaging for children
   - The story must include: {words}
   - Be creative and connect the words naturally

2. A simple image description (1 sentence) to illustrate the story.
   This will be used to generate an image. Keep it simple and colorful.

Return ONLY this JSON format, no extra text:
{{
  "story": "the story here",
  "image_prompt": "colorful children book illustration of ..."
}}
"""

    client = get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=600
    )

    text = response.choices[0].message.content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    return json.loads(text.strip())

# test
if __name__ == "__main__":
    # spelling correction
    correction = correct_words("caet and rayn")
    print("Correction:", correction)
