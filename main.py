import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from bot import bot as money_bot
from wheel_bot import wheel_bot

MONEY_TOKEN = os.getenv("DISCORD_TOKEN")
WHEEL_TOKEN = os.getenv("WHEEL_BOT_TOKEN")

async def main():
    tasks = []
    if MONEY_TOKEN:
        print("[Main] Starting Money Counter bot...", flush=True)
        tasks.append(money_bot.start(MONEY_TOKEN))
    else:
        print("[Main] WARNING: DISCORD_TOKEN is missing!", flush=True)

    if WHEEL_TOKEN:
        print("[Main] Starting Wheel of Pep bot...", flush=True)
        tasks.append(wheel_bot.start(WHEEL_TOKEN))
    else:
        print("[Main] NOTE: WHEEL_BOT_TOKEN is not set. Only running Money Counter.", flush=True)

    if tasks:
        await asyncio.gather(*tasks)
    else:
        print("[Main] No bot tokens provided. Exiting.", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
