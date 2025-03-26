import os
import telegram
import asyncio
import logging

logging.basicConfig(level=logging.INFO)

async def send_failure_notification():
    bot = telegram.Bot(token=os.environ['TELEGRAM_BOT_TOKEN'])
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    message = "❌ <b>Workflow Failed</b>\nThe Tor bridge fetching process encountered an error. Please check the logs for details."
    await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
    logging.info("Failure notification sent to Telegram.")

if __name__ == "__main__":
    asyncio.run(send_failure_notification())