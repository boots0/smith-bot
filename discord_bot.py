# discord_bot.py
# This bot acts as a bridge between Discord and an n8n.io workflow.
# Final production-ready version.

import discord
import os
import requests
import threading
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# --- Enhanced Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. Load Environment Variables ---
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
N8N_WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL")

# --- 2. Basic Bot Sanity Checks ---
if not DISCORD_BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN not found in environment variables. Please set it.")
if not N8N_WEBHOOK_URL:
    raise ValueError("N8N_WEBHOOK_URL not found in environment variables. Please set it.")

# --- 3. Discord Bot Setup ---
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True 
client = discord.Client(intents=intents)

# --- 4. Flask Web Server Setup ---
# Gunicorn will run this 'app' object.
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
def receive_n8n_response():
    try:
        data = request.json
        channel_id = int(data['channel_id'])
        message_content = data['message']
        logging.info(f"Received response from n8n for channel {channel_id}")
        client.loop.create_task(send_message_to_channel(channel_id, message_content))
        return jsonify({"status": "success"}), 200
    except Exception as e:
        logging.error(f"Error in /webhook endpoint: {e}", exc_info=True)
        return jsonify({"status": "error", "details": str(e)}), 500

async def send_message_to_channel(channel_id: int, message: str):
    try:
        channel = await client.fetch_channel(channel_id)
        if channel:
            await channel.send(message)
            logging.info(f"Successfully sent message to channel {channel_id}")
        else:
            logging.error(f"Could not find channel with ID {channel_id}")
    except Exception as e:
        logging.error(f"Error sending message to channel {channel_id}: {e}", exc_info=True)

# --- 5. Discord Event Handlers ---
@client.event
async def on_ready():
    logging.info(f'Bot is logged in as {client.user}')
    logging.info('Ready to receive commands!')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!Smith '):
        # Note: we get the original casing of the query now for the AI
        query_full_case = message.content[len('!Smith '):].strip()
        query_lower = query_full_case.lower()
        channel_id = message.channel.id
        
        # --- STATIC COMMAND HANDLER ---
        if query_lower == "who is that guy?":
            logging.info(f"STATIC COMMAND MATCH: 'who is that guy?' in channel {channel_id}")
            await message.channel.send("<:thisguy:1389678025607479396>") # User's correct emoji ID
            return

        # --- AI WORKFLOW ---
        logging.info(f"AI COMMAND RECEIVED in channel {channel_id}: '{query_full_case}'")
        await message.channel.send(f"Got it. Analyzing your request: `{query_full_case}`. Please wait...")

        payload = {
            "query": query_full_case, # Send original query casing
            "channel_id": str(channel_id),
            "user": message.author.name
        }
        
        logging.info(f"Preparing to send POST request to: {N8N_WEBHOOK_URL}")
        logging.info(f"Payload: {payload}")
        try:
            response = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=15)
            logging.info(f"Received response from n8n. Status Code: {response.status_code}")
            response.raise_for_status()
            logging.info("Successfully sent data to n8n.")
        except requests.exceptions.RequestException as e:
            logging.error(f"CRITICAL: Error sending data to n8n: {e}", exc_info=True)
            await message.channel.send("Sorry, there was a critical error communicating with my analysis service. Please check the logs.")

# --- 6. Start the Discord bot client ---
# The Flask app is started by Gunicorn (from the Procfile), not here.
# This part of the script just needs to start the Discord bot.
def run_bot():
    client.run(DISCORD_BOT_TOKEN)

# Start the bot in a separate thread
bot_thread = threading.Thread(target=run_bot)
bot_thread.start()
