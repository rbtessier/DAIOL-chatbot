import os
import secrets
from datetime import timedelta
from typing import Dict, Any

from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import AzureOpenAI

# ------------------------------------------------------------------------------
# Flask setup
# ------------------------------------------------------------------------------
app = Flask(__name__)
# In production, set this to the exact origin of your Static Web App
CORS(app, resources={r"/api/*": {"origins": "*"}})

app.config["JSON_SORT_KEYS"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)

# ------------------------------------------------------------------------------
# Session store (replace with Redis/Azure Cache for Redis in production)
# ------------------------------------------------------------------------------
# Structure:
# user_sessions[token] = {
#   "messages": [{"role": "...", "content": "..."}],
#   "meta": {"userName": "...", "cohortId": "...", "systemPrompt": "...", "initialMessage": "..."},
#   "model": "deployment-name",
#   "default_temperature": 0.2,
#   "default_max_completion_tokens": 512,
# }
user_sessions: Dict[str, Dict[str, Any]] = {}

# ------------------------------------------------------------------------------
# Defaults
# ------------------------------------------------------------------------------
BASE_SYSTEM_PROMPT = (
    "You are McAllister and you are a guide for a course in organizational leadership, data and AI. "
    "You are not a model, but a course copilot at McMaster University. The title of the course is Data Science, "
    "Applied AI, and Organizational Leadership. This program is offered as a Graduate Academic Certificate and is for "
    "credit at the DeGroote School of Business at McMaster University in Canada. You blend cutting-edge Data Science, "
    "Analytics, AI, Strategy, Leadership and Organizational development to help professionals from any sphere. "
    "Answer with concrete examples drawn from business cases. The audience is professionals, leaders and strategists "
    "leveraging AI to improve their organizations."
)

# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------
def generate_session_token() -> str:
    return secrets.token_hex(32)  # 64-char hex

def extract_token(auth_header: str | None) -> str | None:
    """Accepts either raw token or 'Bearer <token>' for compatibility."""
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None

def get_azure_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
    )

def build_system_prompt(system_prompt_from_client: str | None, meta: Dict[str, Any]) -> str:
    """Use the provided system prompt if present, otherwise the base prompt.
    Optionally enrich with meta so the assistant can personalize output."""
    base = (system_prompt_from_client or "").strip() or BASE_SYSTEM_PROMPT
    extras = []
    user_name = (meta.get("userName") or "").strip()
    cohort_id = (meta.get("cohortId") or "").strip()
    if user_name:
        extras.append(f"Learner name: {user_name}. Address them by name when natural.")
    if cohort_id:
        extras.append(f"Learner cohort: {cohort_id}.")
    if extras:
        base = base.rstrip() + "\n\n" + "\n".join(extras)
    return base

# ------------------------------------------------------------------------------
# Routes
# ------------------------------------------------------------------------------
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

@app.route("/api/start", methods=["POST", "GET"])
def start_session():
    """
    Accepts:
      - userName        (str)
      - cohortId        (str)
      - systemPrompt    (str)  -> overrides default prompt if provided
      - initialMessage  (str)  -> welcome message to display on the frontend

    POST JSON (recommended) or GET query params are both supported.
    Returns: { token, initialMessage }
    """
    if request.method == "POST" and request.is_json:
        payload = request.get_json(silent=True) or {}
    else:
        # GET fallback for simple integrations
        payload = {
            "userName": request.args.get("userName"),
            "cohortId": request.args.get("cohortId"),
            "systemPrompt": request.args.get("systemPrompt"),
            "initialMessage": request.args.get("initialMessage"),
        }

    # Extract and normalize
    user_name = (payload.get("userName") or "").strip() or None
    cohort_id = (payload.get("cohortId") or "").strip() or None
    system_prompt_from_client = (payload.get("systemPrompt") or "").strip() or None
    initial_message = (payload.get("initialMessage") or "").strip() or (
        "Hi, I’m McAllister, your copilot and guide through the Data Science, Applied AI and Organizational Leadership program at DeGroote."
    )

    # Create meta and system prompt
    meta = {
        "userName": user_name,
        "cohortId": cohort_id,
        "systemPrompt": system_prompt_from_client,
        "initialMessage": initial_message,
    }
    system_prompt = build_system_prompt(system_prompt_from_client, meta)

    # Create a new session
    token = generate_session_token()
    user_sessions[token] = {
        "messages": [{"role": "system", "content": system_prompt}],
        "meta": meta,
        "model": os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-5-mini"),
        "default_temperature": float(os.environ.get("DEFAULT_TEMPERATURE", "0.2")),
        "default_max_completion_tokens": int(os.environ.get("DEFAULT_MAX_COMPLETION_TOKENS", "512")),
    }

    # Return token and initial message (frontend renders welcome without burning tokens)
    return jsonify({"token": token, "initialMessage": initial_message})

@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Body JSON:
      - message        (required)
      - temperature    (optional float)
        - max_completion_tokens (optional int)
      - context        (optional str) -> transient, injected as a one-off system note
    Header:
      - Authorization: <token> OR Authorization: Bearer <token>
    """
    token = extract_token(request.headers.get("Authorization"))
    if not token or token not in user_sessions:
        return jsonify({"error": "Invalid session token"}), 401

    if not request.is_json:
        return jsonify({"error": "Expected JSON body"}), 400

    data = request.get_json(silent=True) or {}
    user_message = data.get("message")
    if not user_message or not isinstance(user_message, str):
        return jsonify({"error": "Missing 'message'"}), 400

    temperature = data.get("temperature", user_sessions[token]["default_temperature"])
    max_completion_tokens = data.get(
        "max_completion_tokens",
        user_sessions[token]["default_max_completion_tokens"],
    )
    per_request_context = data.get("context")

    session = user_sessions[token]

    # Inject transient context if provided (doesn't persist across turns)
    if per_request_context:
        session["messages"].append({
            "role": "system",
            "content": f"Context for this turn: {per_request_context}"
        })

    # Append user message
    session["messages"].append({"role": "user", "content": user_message})

    try:
        client = get_azure_client()
        completion = client.chat.completions.create(
            model=session["model"],                 # Azure deployment name
            messages=session["messages"],           # full history
            temperature=float(temperature),
            max_completion_tokens=int(max_completion_tokens),
        )
        response_text = completion.choices[0].message.content

        # Append assistant reply to history
        session["messages"].append({"role": "assistant", "content": response_text})

        return jsonify({"response": response_text})
    except Exception as e:
        # Log the exception in real apps (App Insights, etc.)
        print("Azure OpenAI error:", repr(e))
        return jsonify({"error": "Sorry, I encountered an error."}), 500

@app.route("/api/reset", methods=["POST"])
def reset_session():
    """
    Resets the conversation back to a single system message built from stored meta.
    """
    token = extract_token(request.headers.get("Authorization"))
    if not token or token not in user_sessions:
        return jsonify({"error": "Invalid session token"}), 401

    meta = user_sessions[token].get("meta", {})
    system_prompt = build_system_prompt(meta.get("systemPrompt"), meta)
    user_sessions[token]["messages"] = [{"role": "system", "content": system_prompt}]
    return jsonify({"ok": True})

# ------------------------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # NEVER use debug=True in production
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
