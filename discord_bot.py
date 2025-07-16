# discord_bot.py
# This bot acts as a bridge between Discord and an n8n.io workflow.
# Updated for robust hosting on platforms like Railway.

import discord
import os
import requests
import threading
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# --- 1. Load Environment Variables ---
# Load secrets and configuration from a .env file for local development.
# On a hosting service like Railway, these will be set in the project's dashboard.
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

# --- Hosting Environment Improvement ---
# Hosting platforms like Railway provide a dynamic PORT variable.
# We should use that if it exists, otherwise fall back to our custom variable for local testing.
PORT = os.getenv("PORT", os.getenv("BOT_WEBHOOK_PORT", 8080))


# --- 2. Basic Bot Sanity Checks ---
if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN not found in environment variables. Please set it.")
if not N8N_WEBHOOK_URL:
    raise ValueError("N8N_WEBHOOK_URL not found in environment variables. Please set it.")

# --- 3. Discord Bot Setup ---
# We need to specify 'intents' to tell Discord what events our bot wants to receive.
# 'guilds' for server information, 'messages' for reading messages, and 'message_content'
# is a privileged intent required to read the content of messages.
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True 

# The client is our connection to Discord.
client = discord.Client(intents=intents)

# --- 4. Flask Web Server Setup ---
# This simple web server will run in the background to receive the final response
# from your n8n workflow.
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def receive_n8n_response():
    """
    This endpoint listens for a POST request from your n8n workflow.
    n8n should send a JSON payload like:
    {
        "channel_id": "123456789012345678",
        "message": "This is the analysis result from the LLM."
    }
    """
    try:
        data = request.json
        channel_id = int(data['channel_id'])
        message_content = data['message']

        # We need to run the Discord sending part in an async-safe way.
        # client.loop is the bot's running event loop.
        client.loop.create_task(send_message_to_channel(channel_id, message_content))
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Error in /webhook: {e}")
        return jsonify({"status": "error", "details": str(e)}), 500

async def send_message_to_channel(channel_id: int, message: str):
    """
    Asynchronously sends a message to a specific Discord channel.
    """
    try:
        channel = await client.fetch_channel(channel_id)
        if channel:
            await channel.send(message)
        else:
            print(f"Error: Could not find channel with ID {channel_id}")
    except Exception as e:
        print(f"Error sending message to channel {channel_id}: {e}")

# --- 5. Discord Event Handlers ---
@client.event
async def on_ready():
    """
    This function is called once the bot has successfully connected to Discord.
    """
    print(f'Bot is logged in as {client.user}')
    print(f'Ready to receive commands on port {PORT}!')

@client.event
async def on_message(message):
    """
    This function is called every time a message is sent in a channel the bot can see.
    """
    # Ignore messages sent by the bot itself to prevent loops.
    if message.author == client.user:
        return

    # Check if the message starts with our command prefix.
    if message.content.startswith('!Smith '):
        # Extract the actual query from the message.
        query = message.content[len('!Smith '):].strip()
        
        # Get the channel ID to know where to send the response back.
        channel_id = message.channel.id
        
        print(f"Received query from channel {channel_id}: '{query}'")
        
        # Let the user know the bot is working on it.
        await message.channel.send(f"Got it. Analyzing your request: `{query}`. Please wait...")

        # Prepare the data payload for the n8n webhook.
        payload = {
            "query": query,
            "channel_id": str(channel_id), # Send as string for compatibility
            "user": message.author.name
        }

        # Send the data to your n8n workflow.
        try:
            response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=10)
            response.raise_for_status() # Raises an exception for bad status codes (4xx or 5xx)
            print(f"Successfully sent data to n8n. Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error sending data to n8n: {e}")
            await message.channel.send("Sorry, there was an error communicating with my analysis service. Please try again later.")

# --- 6. The Bridge: Running Flask and Discord Bot Together ---
def run_flask_app():
    """
    Runs the Flask app on the specified port.
    'host="0.0.0.0"' makes it accessible from outside the container/machine.
    """
    app.run(host='0.0.0.0', port=int(PORT))

if __name__ == '__main__':
    # Run the Flask app in a separate thread.
    # This is crucial so the web server doesn't block the Discord bot.
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.daemon = True
    flask_thread.start()

    # Run the Discord bot. This is a blocking call.
    client.run(DISCORD_BOT_TOKEN)
