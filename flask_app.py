import asyncio
from flask import Flask, request
from telegram import Update
from bot import application

app = Flask(__name__)

_initialized = False


@app.route("/")
def index():
    return "Bot is running!"


@app.route("/webhook", methods=["POST"])
def webhook():
    global _initialized
    try:
        data = request.get_json(force=True)
        update = Update.de_json(data, application.bot)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if not _initialized:
            loop.run_until_complete(application.initialize())
            _initialized = True

        loop.run_until_complete(application.process_update(update))
        loop.close()
        print("OK", flush=True)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
    return "OK", 200
