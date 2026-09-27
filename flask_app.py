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

        async def run():
            await application.initialize()
            await application.process_update(update)

        asyncio.run(run())
        print("OK: Update processed", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
    return "OK", 200
