import os
import telegram
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

async def send_failure_notification():
    workflow_end_time = datetime.utcnow()
    workflow_start_time_str = os.environ.get('WORKFLOW_START_TIME', workflow_end_time.strftime('%Y-%m-%dT%H:%M:%SZ'))
    workflow_start_time = datetime.strptime(workflow_start_time_str, '%Y-%m-%dT%H:%M:%SZ')
    total_duration = (workflow_end_time - workflow_start_time).total_seconds()

    bot = telegram.Bot(token=os.environ['TELEGRAM_BOT_TOKEN'])
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    message = (
        f"❌ <b>Workflow Failed</b>\n"
        f"Workflow Start Time: {workflow_start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"Total Duration: {total_duration:.2f} seconds\n"
        f"The Tor bridge fetching process encountered an error. Please check the logs for details."
    )
    await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
    logging.info("Failure notification sent to Telegram.")

if __name__ == "__main__":
    asyncio.run(send_failure_notification())