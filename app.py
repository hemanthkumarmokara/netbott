import openai
import os
import certifi
import re
import requests
import urllib3
from flask import Flask, request, jsonify, render_template, session
import httpx
# Add this import at the top
from routing_checker import is_routing_possible


app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Required for session storage

# Use latest SSL certificates
os.environ["SSL_CERT_FILE"] = certifi.where()

# Disable SSL verification warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Azure OpenAI API Details
AZURE_OPENAI_API_KEY = ""
AZURE_OPENAI_ENDPOINT = ""
AZURE_DEPLOYMENT_NAME = "gpt-4"  # Name of the deployment in Azure

openai.api_type = "azure"
openai.api_key = AZURE_OPENAI_API_KEY
openai.api_base = AZURE_OPENAI_ENDPOINT
openai.api_version = "2023-12-01-preview"

# Override OpenAI request session to disable SSL verification
openai.requestssession = requests.Session()
openai.requestssession.verify = False  # Disable SSL verification

# Function to extract IP addresses
def extract_ips(text):
    ip_pattern = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    return re.findall(ip_pattern, text)

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json.get("message")
    if not user_input:
        return jsonify({"error": "Message cannot be empty"}), 400

    extracted_ips = extract_ips(user_input)

    # Retrieve stored IPs
    stored_ip = session.get("stored_ip", None)
    
    if len(extracted_ips) == 2:  # User provided both IPs
        source_ip, destination_ip = extracted_ips
        session.pop("stored_ip", None)  # Clear stored IP after use
    elif len(extracted_ips) == 1:  # Only one IP provided
        if stored_ip:
            source_ip, destination_ip = stored_ip, extracted_ips[0]
            session.pop("stored_ip", None)  # Clear stored IP after use
        else:
            session["stored_ip"] = extracted_ips[0]
            return jsonify({"response": "You provided one IP. Please enter the destination IP."})
    else:
        source_ip, destination_ip = "N/A", "N/A"
    # After determining source_ip and destination_ip
    # routing_status = is_routing_possible(source_ip, destination_ip)
    routing_status = "N/A"
    if source_ip != "N/A" and destination_ip != "N/A":
        routing_status = is_routing_possible(source_ip, destination_ip)
    # Define the prompt using prompt engineering with examples
    chat_prompt = [
        {
            "role": "system",
            "content": (
                "You are NetBot, a GWAN assistant that helps users check network routing and diagnose connectivity issues.\n\n"
                "Your tasks:\n"
                "- Guide users in finding routing paths.\n"
                "- Request missing IP addresses when needed.\n"
                "- Provide answers based on networking best practices.\n\n"
                "**Examples:**\n"
                "- User: 'Is 12.3.46.4 reachable?'\n"
                "  - NetBot: 'You provided only one IP. Please enter the destination IP to check the reachability.'\n"
                "- User: 'Check route between 10.1.1.1 and 10.2.2.2'\n"
                "  - NetBot: 'Checking the routing table... Route from 10.1.1.1 to 10.2.2.2 is via 192.168.1.1, using MPLS label 300.'\n"
                "- User: 'Which router is handling 192.168.10.1?'\n"
                "  - NetBot: '192.168.10.1 is handled by Router R1, with RD 65000:100 and RT 65000:200.'\n\n"
                "- User: '32.2.34.2'\n"
                "  - NetBot: 'You provided ony one IP. Let me know what you wanted to do with that'\n\n"
                "- User: 'Can 192.168.5.5 communicate with 10.0.5.5?'\n"
                "  - NetBot: 'Checking the routing between given IPs 192.168.5.5 and 10.0.5.5.'\n\n"                                
                "When responding, always ensure clarity and relevance to networking concepts."
            )
        },
        {"role": "user", "content": user_input}
    ]

    try:
        client = openai.AzureOpenAI(
                    api_key=AZURE_OPENAI_API_KEY,
                        api_version="2023-12-01-preview",
                            azure_endpoint=AZURE_OPENAI_ENDPOINT,
                             http_client=httpx.Client(verify=False)  
                            )
        response = client.chat.completions.create(
                    model=AZURE_DEPLOYMENT_NAME,  # Use `model` instead of `deployment_id`
                        messages=chat_prompt,
                            temperature=0.7
                            )
        bot_reply = response.choices[0].message.content

        #bot_reply = response["choices"][0]["message"]["content"]
        if source_ip != "N/A" and destination_ip != "N/A":
            routing_result = is_routing_possible(source_ip, destination_ip)
            bot_reply += f"\n\n➡️ Routing Check Result: {routing_result}"

        return jsonify({
            "response": bot_reply,
            "source_ip": source_ip,
            "destination_ip": destination_ip
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)

