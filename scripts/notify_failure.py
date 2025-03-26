import os
import telegram
import asyncio
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

async def send_failure_notification():
    # زمان شروع باید از Workflow پاس بشه، اینجا به صورت موقت فرض می‌کنیم
    workflow_end_time = datetime.utcnow()
    # برای تست، فرض می‌کنیم Workflow 10 ثانیه پیش شروع شده
    workflow_start_time = workflow_end_time - timedelta(seconds=10)
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
    from datetime import timedelta  # برای تست موقت
    asyncio.run(send_failure_notification())