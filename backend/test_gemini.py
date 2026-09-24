from google import genai
from dotenv import load_dotenv
import os
import json

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("Set GEMINI_API_KEY in backend/.env before running this script.")

client = genai.Client(api_key=api_key)


# --- Test 2: classification ---
CATEGORIES = ["Fee", "Result", "Attendance", "Degree", "IT Support", "Enrollment", "General"]

def classify_query(subject: str, body: str) -> dict:
    prompt = f"""
    Classify this university student email into exactly one of these categories:
    {", ".join(CATEGORIES)}

    Subject: {subject}
    Body: {body}

    Respond ONLY with valid JSON in this exact format, no other text, no markdown:
    {{"category": "...", "confidence": 0.0}}
    """
    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents=prompt
    )
    text = response.text.strip()
    text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(text)


if __name__ == "__main__":
    response = client.models.generate_content(
        model="gemini-flash-lite-latest",
        contents="Say hello in one short sentence.",
    )
    print("Connection test:", response.text)
    result = classify_query(
        subject="Fee refund not received",
        body="I paid my fee last week but the portal still shows unpaid. Please check.",
    )
    print("Classification test:", result)
