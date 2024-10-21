from openai import AzureOpenAI
from flask import Flask, request, jsonify
import json
from uuid import uuid4

app = Flask(__name__)

# Store conversation history for each token
user_sessions = {}

@app.route("/api/start", methods=["GET"])
def start_session():
    # Generate a new session token
    session_token = str(uuid4())
    # Initialize an empty conversation history for this token
    user_sessions[session_token] = []
    
    # Return the session token to the client
    return jsonify({"token": session_token})

@app.route("/api/chat", methods=["POST"])
def chat():
    # Retrieve the session token from the request
    session_token = request.headers.get("Authorization")
    
    if not session_token or session_token not in user_sessions:
        return jsonify({"error": "Invalid session token"}), 401
    
    data = request.json
    user_message = data.get("message")
    
    # Append user message to the conversation history
    user_sessions[session_token].append({"role": "user", "content": user_message})
    
    # Get AI response using the conversation history
    response = get_ai_response(user_sessions[session_token])
    
    # Append the AI response to the conversation history
    user_sessions[session_token].append({"role": "assistant", "content": response})
    
    return jsonify({"response": response})

def get_ai_response(conversation_history):
    try:
        client = AzureOpenAI(
            api_key="a7c02d6cccc44acaa1207229de52ef26",
            api_version="2024-08-01-preview",
            azure_endpoint="https://open-ai-service-class.openai.azure.com/",
        )

        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=100,
            messages=conversation_history,
        )
        return completion.choices[0].message.content
    except Exception as e:
        return "Sorry, I encountered an error."

if __name__ == "__main__":
    app.run(debug=True)
