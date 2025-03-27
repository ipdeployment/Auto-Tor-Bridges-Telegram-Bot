import json
import logging
import os

logging.basicConfig(level=logging.INFO)

def update_bridges():
    try:
        files = [
            "config/obfs4_ipv4.json",
            "config/obfs4_ipv6.json",
            "config/webtunnel_ipv4.json",
            "config/webtunnel_ipv6.json"
        ]
        for file in files:
            if not os.path.exists(file):
                with open(file, "w") as f:
                    json.dump({"bridges": []}, f, indent=4)
                logging.info(f"Created {file}")
            else:
                with open(file, "r") as f:
                    data = json.load(f)
                sorted_bridges = sorted(set(data.get("bridges", [])))
                with open(file, "w") as f:
                    json.dump({"bridges": sorted_bridges}, f, indent=4)
                logging.info(f"Sorted and updated {file} with {len(sorted_bridges)} bridges.")
        logging.info("Bridge files checked/updated successfully.")
    except Exception as e:
        logging.error(f"Error updating bridges: {e}")

if __name__ == "__main__":
    update_bridges()