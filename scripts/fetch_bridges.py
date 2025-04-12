import requests
from bs4 import BeautifulSoup
import telegram
import asyncio
import os
import json
import logging
import random
import subprocess
import shutil
import time
from datetime import datetime
import stem.control
from stem import Signal

logging.basicConfig(level=logging.INFO)

HISTORY_FILE = "config/history.json"
FAILED_BRIDGES_FILE = "config/failed_bridges.json"
OBFS4_IPV4_FILE = "config/obfs4_ipv4.json"
TEMP_DIR = "temp"

def ensure_temp_dir():
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)

def reset_tor():
    subprocess.run(["pkill", "-f", "tor"], check=False)
    if os.path.exists(TEMP_DIR):
        shutil.rmtree(TEMP_DIR)
    os.makedirs(TEMP_DIR)

def load_history():
    default_history = {"last_bridge": None, "used_bridges": []}
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
            if "last_bridge" not in history:
                history["last_bridge"] = None
            if "used_bridges" not in history:
                history["used_bridges"] = []
            return history
    except (FileNotFoundError, json.JSONDecodeError):
        save_history(default_history["last_bridge"], default_history["used_bridges"])
        return default_history

def save_history(last_bridge, used_bridges):
    history = {"last_bridge": last_bridge, "used_bridges": used_bridges}
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=4)

def load_failed_bridges():
    try:
        with open(FAILED_BRIDGES_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"failed_bridges": {}, "attempts": {}}

def save_failed_bridge(bridge):
    failed_data = load_failed_bridges()
    failed_bridges = failed_data.get("failed_bridges", {})
    attempts = failed_data.get("attempts", {})
    
    attempts[bridge] = attempts.get(bridge, 0) + 1
    if attempts[bridge] >= 2:
        failed_bridges[bridge] = True
        logging.info(f"Bridge blacklisted after 2 failures: {bridge}")
    
    with open(FAILED_BRIDGES_FILE, "w") as f:
        json.dump({"failed_bridges": failed_bridges, "attempts": attempts}, f, indent=4)

def load_obfs4_ipv4_bridges():
    try:
        with open(OBFS4_IPV4_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("bridges", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def load_all_existing_bridges():
    bridge_files = {
        "obfs4_ipv4": "config/obfs4_ipv4.json",
        "obfs4_ipv6": "config/obfs4_ipv6.json",
        "webtunnel_ipv4": "config/webtunnel_ipv4.json",
        "webtunnel_ipv6": "config/webtunnel_ipv6.json"
    }
    all_bridges = set()
    for file_path in bridge_files.values():
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                all_bridges.update(data.get("bridges", []))
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return all_bridges

def start_tor(bridge, port=9051):
    reset_tor()  # بازنشانی کامل Tor قبل از شروع
    torrc = f"""
    UseBridges 1
    ClientTransportPlugin obfs4 exec /usr/bin/obfs4proxy
    Bridge {bridge}
    SocksPort {port}
    ControlPort 9052
    Log notice file {TEMP_DIR}/tor.log
    """
    torrc_file = f"{TEMP_DIR}/torrc_test"
    log_file = f"{TEMP_DIR}/tor.log"
    with open(torrc_file, "w") as f:
        f.write(torrc.strip())

    if os.path.exists(log_file):
        os.remove(log_file)
    process = subprocess.Popen(["tor", "-f", torrc_file])
    max_wait = 180
    for _ in range(max_wait // 10):
        time.sleep(10)
        if os.path.exists(log_file):
            with open(log_file, "r") as log:
                log_content = log.read()
                if "Bootstrapped 100%" in log_content:
                    logging.info(f"Tor bootstrapped successfully with bridge: {bridge}")
                    # درخواست مدار جدید
                    try:
                        with stem.control.Controller.from_port(port=9052) as controller:
                            controller.authenticate()
                            controller.signal(Signal.NEWNYM)
                            logging.info("Requested new Tor circuit")
                    except Exception as e:
                        logging.error(f"Failed to request new circuit: {e}")
                    return process
    process.terminate()
    logging.error(f"Tor failed to bootstrap with bridge: {bridge}")
    return None

async def fetch_bridges():
    urls = {
        "obfs4_ipv4": "https://bridges.torproject.org/bridges?transport=obfs4",
        "obfs4_ipv6": "https://bridges.torproject.org/bridges?transport=obfs4&ipv6=yes",
        "webtunnel_ipv4": "https://bridges.torproject.org/bridges?transport=webtunnel",
        "webtunnel_ipv6": "https://bridges.torproject.org/bridges?transport=webtunnel&ipv6=yes"
    }

    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0",
    ]
    headers = {
        "User-Agent": random.choice(user_agents),
        "Referer": "https://bridges.torproject.org/",
        "Accept-Language": "en-US,en;q=0.9",
    }

    history = load_history()
    used_bridges = history["used_bridges"]
    failed_data = load_failed_bridges()
    failed_bridges = set(failed_data.get("failed_bridges", {}).keys())
    default_bridges = [
        "obfs4 72.10.162.51:12693 8F219F64DC11351F00C3A50B64990EE50E784F74 cert=/I3NYd0UcxUh83Xmsj2j8GNOeNBHmJ8jspO0/3ijqKxAlIBedJ9/AC80fXkY6IyEwXYzQQ iat-mode=1",
        # می‌توانید پل‌های معتبر دیگر را اضافه کنید
    ]

    ensure_temp_dir()
    obfs4_ipv4_bridges = load_obfs4_ipv4_bridges() - set(used_bridges[-1:]) - failed_bridges
    available_bridges = list(obfs4_ipv4_bridges) + default_bridges
    if not available_bridges:
        logging.error("No available bridges to use.")
        return None, None

    tor_process = None
    selected_bridge = None
    for bridge in random.sample(available_bridges, len(available_bridges)):
        logging.info(f"Trying bridge: {bridge}")
        tor_process = start_tor(bridge)
        if tor_process:
            selected_bridge = bridge
            break
        save_failed_bridge(bridge)

    if not tor_process:
        logging.error("No working Tor bridge found.")
        return None, None

    proxies = {
        'http': 'socks5h://127.0.0.1:9051',
        'https': 'socks5h://127.0.0.1:9051'
    }

    all_bridges = {}
    for name, url in urls.items():
        for attempt in range(5):
            try:
                response = requests.get(url, headers=headers, proxies=proxies, timeout=30)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')

                bridge_elements = soup.find_all('pre', class_='bridge-line')[:5]
                bridges = [element.text.strip() for element in bridge_elements if element.text.strip() not in failed_bridges]

                if not bridges:
                    all_text = soup.get_text()
                    if 'obfs4' in name:
                        bridges = [line.strip() for line in all_text.split('\n') if 'obfs4' in line and 'cert=' in line and line.strip() not in failed_bridges][:5]
                    elif 'webtunnel' in name:
                        bridges = [line.strip() for line in all_text.split('\n') if 'webtunnel' in line and 'http' in line and line.strip() not in failed_bridges][:5]

                all_bridges[name] = bridges
                break
            except requests.RequestException as e:
                logging.error(f"Failed to fetch {url}: {e}")
                if attempt == 4:
                    continue
                time.sleep(10)

    if not all_bridges:
        tor_process.terminate()
        return None, None

    used_bridges.append(selected_bridge)
    save_history(selected_bridge, used_bridges)

    return all_bridges, tor_process

async def send_telegram_message(bot, chat_id, message):
    for i in range(0, len(message), 4096):
        await bot.send_message(chat_id=chat_id, text=message[i:i+4096], parse_mode="HTML")

async def send_bridges_file(bot, chat_id, bridges_dict):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    bridges_file = f"{TEMP_DIR}/bridges_{timestamp}.txt"
    with open(bridges_file, "w") as f:
        for bridge_type, bridges in bridges_dict.items():
            if bridges:
                f.write(f"{bridge_type.replace('_', ' ').capitalize()}:\n")
                for bridge in bridges:
                    f.write(f"{bridge}\n\n")
    if os.path.getsize(bridges_file) > 0:
        with open(bridges_file, "rb") as f:
            await bot.send_document(chat_id=chat_id, document=f, caption=f"Tor Bridges {timestamp}")

async def send_qr_zip(bot, chat_id, bridges_dict):
    ensure_temp_dir()
    qr_dir = f"{TEMP_DIR}/qr_codes"
    if not os.path.exists(qr_dir):
        os.makedirs(qr_dir)

    for bridge_type, bridges in bridges_dict.items():
        for i, bridge in enumerate(bridges):
            qr_file = f"{qr_dir}/{bridge_type}_{i}.png"
            subprocess.run(["qrencode", "-o", qr_file, bridge])

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    seven_zip_file = f"{TEMP_DIR}/bridges_qr_codes_{timestamp}.7z"
    subprocess.run(["7z", "a", seven_zip_file, f"{qr_dir}/*"])

    with open(seven_zip_file, "rb") as f:
        await bot.send_document(chat_id=chat_id, document=f, caption="QR Codes for Tor Bridges")

def append_to_json(file_path, new_bridges, all_existing_bridges):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"bridges": []}

    unique_new_bridges = [b for b in new_bridges if b not in all_existing_bridges]
    data["bridges"].extend(unique_new_bridges)
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)
    return unique_new_bridges

def rewrite_and_sort_json_files(bridges_dict):
    bridge_files = {
        "obfs4_ipv4": "config/obfs4_ipv4.json",
        "obfs4_ipv6": "config/obfs4_ipv6.json",
        "webtunnel_ipv4": "config/webtunnel_ipv4.json",
        "webtunnel_ipv6": "config/webtunnel_ipv6.json"
    }
    all_bridges = set()
    for bridges in bridges_dict.values():
        all_bridges.update(bridges)

    for bridge_type, file_path in bridge_files.items():
        try:
            with open(file_path, "r") as f:
                data = json.load(f)
                existing_bridges = set(data.get("bridges", []))
        except (FileNotFoundError, json.JSONDecodeError):
            existing_bridges = set()

        if bridge_type in bridges_dict:
            existing_bridges.update(bridges_dict[bridge_type])
        sorted_bridges = sorted(existing_bridges)
        with open(file_path, "w") as f:
            json.dump({"bridges": sorted_bridges}, f, indent=4)
        logging.info(f"Rewrote and sorted {file_path} with {len(sorted_bridges)} bridges.")

async def main():
    bridges, tor_process = await fetch_bridges()
    if bridges is None:
        message = "❌ <b>Failed to connect to Tor network or fetch bridges.</b>\nPlease check logs or try again later."
    else:
        all_existing_bridges = load_all_existing_bridges()
        bridge_files = {
            "obfs4_ipv4": "config/obfs4_ipv4.json",
            "obfs4_ipv6": "config/obfs4_ipv6.json",
            "webtunnel_ipv4": "config/webtunnel_ipv4.json",
            "webtunnel_ipv6": "config/webtunnel_ipv6.json"
        }

        found_any_new = False
        new_bridges_by_type = {}
        for bridge_type, bridge_list in bridges.items():
            unique_new_bridges = append_to_json(bridge_files[bridge_type], bridge_list, all_existing_bridges)
            all_existing_bridges.update(unique_new_bridges)
            new_bridges_by_type[bridge_type] = unique_new_bridges
            if unique_new_bridges:
                found_any_new = True

        if not found_any_new:
            message = "🚀 <b>Latest Tor Bridges:</b>\n\n❌ <b>No new bridges found.</b>\nAll fetched bridges were duplicates."
        else:
            message = "🚀 <b>Latest Tor Bridges:</b>\n\n"
            for bridge_type, unique_new_bridges in new_bridges_by_type.items():
                if unique_new_bridges:
                    message += f"<b>{bridge_type.replace('_', ' ').capitalize()}:</b>\n"
                    for bridge in unique_new_bridges:
                        message += f"<code>{bridge}</code>\n\n"

    bot = telegram.Bot(token=os.environ['TELEGRAM_BOT_TOKEN'])
    chat_id = os.environ['TELEGRAM_CHAT_ID']

    await send_telegram_message(bot, chat_id, message)
    if bridges:
        await send_bridges_file(bot, chat_id, bridges)
        await send_qr_zip(bot, chat_id, bridges)
        rewrite_and_sort_json_files(bridges)

    if tor_process:
        tor_process.terminate()

if __name__ == "__main__":
    asyncio.run(main())