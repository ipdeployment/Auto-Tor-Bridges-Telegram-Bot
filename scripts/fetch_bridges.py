import requests
from bs4 import BeautifulSoup
import telegram
import asyncio
import os
import json
import logging

logging.basicConfig(level=logging.INFO)

async def fetch_bridges():
    urls = {
        "obfs4": "https://bridges.torproject.org/bridges?transport=obfs4",
        "obfs4_ipv6": "https://bridges.torproject.org/bridges?transport=obfs4&ipv6=yes",
        "webtunnel": "https://bridges.torproject.org/bridges?transport=webtunnel",
        "webtunnel_ipv6": "https://bridges.torproject.org/bridges?transport=webtunnel&ipv6=yes"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0",
        "Referer": "https://bridges.torproject.org"
    }

    proxies = {
        'http': 'socks5h://127.0.0.1:9050',
        'https': 'socks5h://127.0.0.1:9050'
    }

    all_bridges = {}
    for name, url in urls.items():
        try:
            response = requests.get(url, headers=headers, proxies=proxies, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract bridges
            bridge_elements = soup.find_all('pre', class_='bridge-line')[:5]  
            bridges = [element.text.strip() for element in bridge_elements]

            if not bridges:
                all_text = soup.get_text()
                if 'obfs4' in name:
                    bridges = [line.strip() for line in all_text.split('\n') if 'obfs4' in line and 'cert=' in line][:5]
                elif 'webtunnel' in name:
                    bridges = [line.strip() for line in all_text.split('\n') if 'webtunnel' in line and 'http' in line][:5]

            all_bridges[name] = bridges
        except requests.RequestException as e:
            logging.error(f"Failed to fetch {url}: {e}")

    return all_bridges

async def send_telegram_message(message):
    bot = telegram.Bot(token=os.environ['TELEGRAM_BOT_TOKEN'])
    chat_id = os.environ['TELEGRAM_CHAT_ID']
    for i in range(0, len(message), 4096):
        await bot.send_message(chat_id=chat_id, text=message[i:i+4096], parse_mode="HTML")

async def main():
    bridges = await fetch_bridges()
    message = "🚀 <b>Latest Tor Bridges:</b>\n\n"
    found_any = False

    for bridge_type, bridge_list in bridges.items():
        message += f"<b>{bridge_type.replace('_', ' ').capitalize()}:</b>\n"
        if bridge_list:
            found_any = True
            for bridge in bridge_list:
                message += f"<code>{bridge}</code>\n\n"
        else:
            message += "<i>❌ No bridges found</i>\n\n"

    if not found_any:
        message += "❌ <b>No bridges found.</b>\nPlease check manually."

    await send_telegram_message(message)

    with open("config/bridges.json", "w") as f:
        json.dump({"bridges": bridges.get("obfs4", [])[:2]}, f, indent=4)

asyncio.run(main())