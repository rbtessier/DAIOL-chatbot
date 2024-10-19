from openai import AzureOpenAI
from flask import Flask, request, jsonify
import json


app = Flask(__name__)

# Set up OpenAI API connection (using environment variables for security)

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message")
    response = get_ai_response(user_message)
    return jsonify({"response": response})

def get_ai_response(user_message):
    try:

        # https://learn.microsoft.com/en-us/azure/ai-services/openai/reference#rest-api-versioning
        client = AzureOpenAI(
            # if no key specified gets the API Key from environment variable AZURE_OPENAI_API_KEY
            api_key = "a7c02d6cccc44acaa1207229de52ef26",
            api_version="2024-08-01-preview",
            # https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource?pivots=web-portal#create-a-resource
            azure_endpoint="https://open-ai-service-class.openai.azure.com/",
        )


        completion = client.chat.completions.create(
        model="gpt-4o-mini",  # e.g. gpt-35-instant
        prompt = user_message
        #messages=[
        #    {
        #        "role": "user",
        #        "content": "Give me a single short riddle",
        #    },
        #],
        )
        return completion.choices[0].text.strip()
    except Exception as e:
        return "Sorry, I encountered an error."

if __name__ == "__main__":
    app.run(debug=True)



