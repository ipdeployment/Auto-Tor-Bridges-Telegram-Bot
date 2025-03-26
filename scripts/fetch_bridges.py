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
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

HISTORY_FILE = "config/history.json"
FAILED_BRIDGES_FILE = "config/failed_bridges.json"
OBFS4_IPV4_FILE = "config/obfs4_ipv4.json"
TEMP_DIR = os.path.abspath("temp")

def ensure_temp_dir():
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
    for subdir in ["logs", "qr"]:
        os.makedirs(os.path.join(TEMP_DIR, subdir), exist_ok=True)
    return TEMP_DIR

def clean_temp_dir():
    base_temp_dir = ensure_temp_dir()
    shutil.rmtree(base_temp_dir, ignore_errors=True)
    os.makedirs(base_temp_dir)
    os.makedirs(os.path.join(base_temp_dir, "logs"))
    os.makedirs(os.path.join(base_temp_dir, "qr"))

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
            return set(json.load(f).get("failed_bridges", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_failed_bridge(bridge):
    failed_bridges = load_failed_bridges()
    failed_bridges.add(bridge)
    with open(FAILED_BRIDGES_FILE, "w") as f:
        json.dump({"failed_bridges": list(failed_bridges)}, f, indent=4)

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

def start_tor(bridge):
    subprocess.run(["pkill", "-f", "tor"], check=False)
    base_temp_dir = ensure_temp_dir()
    torrc = """
    UseBridges 1
    ClientTransportPlugin obfs4 exec /usr/bin/obfs4proxy
    Bridge {bridge}
    SocksPort 9051
    Log notice file {temp_dir}/logs/tor.log
    """.format(bridge=bridge, temp_dir=base_temp_dir)

    torrc_file = os.path.join(base_temp_dir, "torrc_test")
    log_file = os.path.join(base_temp_dir, "logs", "tor.log")
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
                    return process
    process.terminate()
    logging.error(f"Tor failed to bootstrap with bridge: {bridge}")
    return None

async def fetch_bridges(tor_process=None):
    urls = {
        "obfs4_ipv4": "https://bridges.torproject.org/bridges?transport=obfs4",
        "obfs4_ipv6": "https://bridges.torproject.org/bridges?transport=obfs4&ipv6=yes",
        "webtunnel_ipv4": "https://bridges.torproject.org/bridges?transport=webtunnel",
        "webtunnel_ipv6": "https://bridges.torproject.org/bridges?transport=webtunnel&ipv6=yes"
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:91.0) Gecko/20100101 Firefox/91.0",
        "Referer": "https://bridges.torproject.org"
    }

    history = load_history()
    used_bridges = history["used_bridges"]
    failed_bridges = load_failed_bridges()
    default_bridge = "obfs4 72.10.162.51:12693 8F219F64DC11351F00C3A50B64990EE50E784F74 cert=/I3NYd0UcxUh83Xmsj2j8GNOeNBHmJ8jspO0/3ijqKxAlIBedJ9/AC80fXkY6IyEwXYzQQ iat-mode=1"

    ensure_temp_dir()
    if not tor_process:
        obfs4_ipv4_bridges = load_obfs4_ipv4_bridges() - set(used_bridges[-1:]) - failed_bridges
        if obfs4_ipv4_bridges:
            selected_bridge = random.choice(list(obfs4_ipv4_bridges))
        else:
            selected_bridge = default_bridge
        tor_process = start_tor(selected_bridge)
        if not tor_process:
            tor_process = start_tor(selected_bridge)  # Retry once
            if not tor_process:
                save_failed_bridge(selected_bridge)
                return None, None, datetime.now(timezone.utc)

    if not tor_process:
        logging.error("No working Tor process available.")
        return None, None, datetime.now(timezone.utc)

    proxies = {
        'http': 'socks5h://127.0.0.1:9051',
        'https': 'socks5h://127.0.0.1:9051'
    }

    all_bridges = {}
    fetch_start_time = datetime.now(timezone.utc)
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
                    all_bridges[name] = []
                time.sleep(10)

    if not any(all_bridges.values()):
        if tor_process:
            tor_process.terminate()
        return None, None,...

Something went wrong. Please try again.