import json
from flask import Flask, request, jsonify
import requests
import re
import os

SECRET = "kashvi.sharma"

app = Flask(__name__)

def extract_demo_answer(page_html, page_url):
    """
    Simple example: tries to detect numeric answer from page.
    This can be replaced with quiz-specific extraction logic.
    """
    m = re.search(r'sum of the .*?\"value\".*?(\d+)', page_html, re.I | re.S)
    if m:
        return int(m.group(1))
    return 12345  # fallback answer

@app.route("/", methods=["GET"])
def home():
    return (
        "LLM Analysis Quiz API is running.<br>"
        "Use POST /quiz-endpoint to send tasks.",
        200
    )

@app.route("/quiz-endpoint", methods=["POST"])
def quiz_endpoint():
    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "invalid json"}), 400

    email = payload.get("email")
    secret = payload.get("secret")
    url = payload.get("url")

    if not email:
        return jsonify({"error": "missing email"}), 400
    if not secret:
        return jsonify({"error": "missing secret"}), 400
    if not url:
        return jsonify({"error": "missing url"}), 400

    if secret != SECRET:
        return jsonify({"error": "forbidden - invalid secret"}), 403

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60_000)
            page.wait_for_load_state("networkidle", timeout=30_000)
            html = page.content()
            answer = extract_demo_answer(html, url)
            browser.close()
    except Exception as e:
        return jsonify({
            "error": "failed to render page",
            "detail": str(e)
        }), 500

    submit_match = re.search(
        r'https?://[^\s"\'<>]+/submit[^\s"\'<>]*',
        html
    )

    if not submit_match:
        return jsonify({
            "email": email,
            "url": url,
            "answer_candidate": answer
        }), 200

    submit_url = submit_match.group(0)

    submit_payload = {
        "email": email,
        "secret": SECRET,
        "url": url,
        "answer": answer
    }

    try:
        r = requests.post(submit_url, json=submit_payload, timeout=30)
        r.raise_for_status()
        return jsonify({
            "submitted": True,
            "submit_url": submit_url,
            "status_code": r.status_code,
            "response": r.json()
        }), 200

    except Exception as e:
        return jsonify({
            "submitted": False,
            "error": str(e),
            "candidate_answer": answer,
            "submit_url": submit_url
        }), 200
        
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
