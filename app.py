import os

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv
from google import genai
from google.genai import types

from chatbot_config import SYSTEM_PROMPT


load_dotenv()

app = Flask(__name__)

MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")


def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. Please add it to your .env file."
        )

    return genai.Client(api_key=api_key)


def normalize_history(history):
    """Clean and limit conversation history."""
    if not isinstance(history, list):
        return []

    cleaned = []

    for message in history[-20:]:
        if not isinstance(message, dict):
            continue

        role = message.get("role")
        content = message.get("content")

        if role in {"user", "assistant"} and isinstance(content, str):
            content = content.strip()
            if content:
                cleaned.append(
                    {
                        "role": role,
                        "content": content[:8000],
                    }
                )

    return cleaned


def build_prompt(history, message):
    """Build a compact multi-turn prompt for Gemini."""
    conversation = []

    for item in history:
        speaker = "User" if item["role"] == "user" else "EcoGuide"
        conversation.append(f"{speaker}: {item['content']}")

    conversation.append(f"User: {message}")
    return "\n\n".join(conversation)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/chat")
def chat():
    try:
        data = request.get_json(silent=True) or {}
        message = data.get("message", "")
        history = normalize_history(data.get("history", []))

        if not isinstance(message, str):
            return jsonify({"error": "Message must be text."}), 400

        message = message.strip()

        if not message:
            return jsonify({"error": "Please enter a message."}), 400

        if len(message) > 8000:
            return jsonify(
                {"error": "Please keep your message under 8000 characters."}
            ), 400

        client = get_gemini_client()
        prompt = build_prompt(history, message)

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.4,
            ),
        )

        answer = (response.text or "").strip()

        if not answer:
            return jsonify(
                {"error": "I could not generate a response. Please try again."}
            ), 502

        return jsonify({"reply": answer})

    except Exception as exc:
        app.logger.exception("Chat request failed")
        return jsonify(
            {"error": f"Unable to process your request: {str(exc)}"}
        ), 500


@app.get("/health")
def health():
    return jsonify({"status": "ok", "model": MODEL_NAME})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
