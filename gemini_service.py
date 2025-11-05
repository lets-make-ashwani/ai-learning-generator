import os
import requests
import json
import re
from flask import current_app

API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

def _extract_json_array(text):
    if not text or not isinstance(text, str):
        return None
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return None
    json_text = text[start:end+1]
    try:
        return json.loads(json_text)
    except Exception:
        # remove triple-backticks and try again
        cleaned = re.sub(r"```.*?```", "", json_text, flags=re.DOTALL)
        try:
            return json.loads(cleaned)
        except Exception:
            return None

def generate_content(topic: str, num_items: int, mode: str, difficulty: str="Intermediate", include_explanations: bool=False):
    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        if current_app:
            current_app.logger.error("GEMINI_API_KEY not set.")
        return None

    # System prompt
    if mode == "flashcard":
        sys = (
            f"You are an expert educator. Create exactly {num_items} flashcards on the topic: {topic}.\n"
            f"Difficulty: {difficulty}.\n"
            "Return ONLY a JSON array. Each item: {\"question\":\"...\",\"answer\":\"...\"}\n"
            "If possible include an 'explanation' field but it's optional."
        )
    elif mode == "mcq":
        sys = (
            f"You are an expert quiz maker. Create exactly {num_items} multiple-choice questions on: {topic}.\n"
            f"Difficulty: {difficulty}.\n"
            "Return ONLY a JSON array. Each item must be: "
            "{\"question\":\"...\",\"options\":[\"opt1\",\"opt2\",\"opt3\",\"opt4\"],\"correct_answer\":\"optX\",\"explanation\":\"...\"}\n"
            "Make options plausible. Include 'explanation' if include_explanations is True."
        )
    else:
        return None

    payload = {
        "contents": [{"role":"user","parts":[{"text": topic}]}],
        "systemInstruction": {"parts":[{"text": sys}]},
        "generationConfig": {"responseMimeType":"application/json"}
    }

    headers = {"Content-Type":"application/json"}
    url = f"{API_URL}?key={API_KEY}"

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        text = data.get("candidates",[{}])[0].get("content",{}).get("parts",[{}])[0].get("text","")
        items = _extract_json_array(text)
        if not isinstance(items, list):
            if current_app:
                current_app.logger.error("No list parsed from Gemini response.")
            return None

        out = []
        for it in items[:num_items]:
            if mode == "flashcard":
                q = it.get("question") or it.get("front") or it.get("prompt") or ""
                a = it.get("answer") or it.get("back") or ""
                if not q or not a:
                    continue
                out.append({"question": q, "answer": a, "explanation": it.get("explanation","")})
            else:
                question = it.get("question") or ""
                options = it.get("options") or it.get("choices") or []
                correct = it.get("correct_answer") or it.get("answer") or ""
                # normalize options to 4
                options = [str(x) for x in options][:4]
                while len(options) < 4:
                    options.append("N/A")
                if not correct or correct not in options:
                    correct = options[0]
                out.append({"question": question, "options": options, "correct_answer": correct, "explanation": it.get("explanation","")})
        return out if out else None

    except Exception as e:
        if current_app:
            current_app.logger.error(f"Gemini API error: {e}")
        else:
            print("Gemini error:", e)
        return None
