"""Minimal OpenRouter client (OpenAI-compatible chat completions)."""
import json
import re

import requests

URL = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(Exception):
    """Raised with a message that is safe to show to the user."""


def chat(messages, model, api_key, temperature=0.3, max_tokens=3500, timeout=120) -> str:
    if not api_key:
        raise OpenRouterError("No OpenRouter API key found. Add it in the sidebar or in the app secrets.")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://streamlit.io",
        "X-Title": "Westbridge decision review (teaching prototype)",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        resp = requests.post(URL, headers=headers, json=payload, timeout=timeout)
    except requests.RequestException as exc:
        raise OpenRouterError(f"Network problem while calling OpenRouter: {exc}") from exc

    if resp.status_code != 200:
        msg = resp.text
        try:
            err = resp.json().get("error")
            if isinstance(err, dict):
                msg = err.get("message", msg)
            elif isinstance(err, str):
                msg = err
        except ValueError:
            pass
        hint = ""
        if resp.status_code == 401:
            hint = " (OpenRouter did not accept the API key: paste a fresh key, check Secrets, and check your credits.)"
        elif resp.status_code in (400, 404):
            hint = " (Check the model name at openrouter.ai/models.)"
        raise OpenRouterError(f"OpenRouter error {resp.status_code}: {str(msg)[:300]}{hint}")

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise OpenRouterError("Unexpected answer format from OpenRouter.") from exc
    if not content:
        raise OpenRouterError("The model returned an empty answer. Try again or pick another model.")
    return content


def extract_json(text: str) -> dict:
    """Parse JSON from a model reply, even if it is wrapped in code fences or extra text."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE)
    try:
        data = json.loads(t)
    except json.JSONDecodeError:
        start, end = t.find("{"), t.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("No JSON object found")
        data = json.loads(t[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("JSON is not an object")
    return data


def chat_json(messages, model, api_key, retries=1, **kwargs):
    """Call the model and return (parsed_json, raw_text). Retries once if the JSON is broken."""
    msgs = list(messages)
    for _ in range(retries + 1):
        raw = chat(msgs, model, api_key, **kwargs)
        try:
            return extract_json(raw), raw
        except ValueError:
            msgs = msgs + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": "Your reply was not valid JSON. Reply again with ONLY the JSON object and no other text."},
            ]
    raise OpenRouterError("The AI did not return valid JSON. Please try again or choose another model.")
