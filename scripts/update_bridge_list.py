import json
import logging

logging.basicConfig(level=logging.INFO)

def update_bridges():
    try:
        with open("config/bridges.json", "r") as f:
            data = json.load(f)

        new_bridges = data.get("bridges", [])[:2]
        if not new_bridges:
            logging.warning("No new bridges to update.")
            return

        with open("config/bridges.json", "w") as f:
            json.dump({"bridges": new_bridges}, f, indent=4)

        logging.info("Bridges updated successfully.")

    except Exception as e:
        logging.error(f"Error updating bridges: {e}")

if __name__ == "__main__":
    update_bridges()