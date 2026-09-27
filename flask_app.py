import asyncio
from flask import Flask, request
from telegram import Update
from bot import application

app = Flask(__name__)


@app.route("/")
def index():
    return "Bot is running!"


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process(update))
        loop.close()
    except Exception as e:
        print(f"Error: {e}")
    return "OK", 200


async def process(update):
    await application.initialize()
    await application.process_update(update)
