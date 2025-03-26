import json
import logging
import os
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO)

TEMP_DIR = os.path.abspath("temp")

def update_bridges():
    update_start_time = datetime.now(timezone.utc)
    files = [
        "config/obfs4_ipv4.json",
        "config/obfs4_ipv6.json",
        "config/webtunnel_ipv4.json",
        "config/webtunnel_ipv6.json"
    ]
    
    base_temp_dir = TEMP_DIR
    os.makedirs(base_temp_dir, exist_ok=True)
    summary_file = os.path.join(base_temp_dir, "bridge_update_summary.txt")
    
    try:
        with open(summary_file, "w") as sf:
            sf.write(f"Bridge List Update Started: {update_start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            sf.write("----------------------------------------\n\n")

        for file in files:
            if not os.path.exists(file):
                with open(file, "w") as f:
                    json.dump({"bridges": []}, f, indent=4)
                logging.info(f"Created new bridge file: {file}")
                with open(summary_file, "a") as sf:
                    sf.write(f"Created: {file} (No bridges yet)\n")
            else:
                with open(file, "r") as f:
                    data = json.load(f)
                bridges = data.get("bridges", [])
                sorted_bridges = sorted(set(bridges))
                with open(file, "w") as f:
                    json.dump({"bridges": sorted_bridges}, f, indent=4)
                logging.info(f"Sorted and updated {file} with {len(sorted_bridges)} bridges.")
                with open(summary_file, "a") as sf:
                    sf.write(f"Updated: {file} - {len(sorted_bridges)} bridges\n")

        update_end_time = datetime.now(timezone.utc)
        total_duration = (update_end_time - update_start_time).total_seconds()
        
        with open(summary_file, "a") as sf:
            sf.write("\n----------------------------------------\n")
            sf.write(f"Update Completed: {update_end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
            sf.write(f"Total Duration: {total_duration:.2f} seconds\n")
        
        logging.info("Bridge files checked/updated successfully.")
    
    except Exception as e:
        logging.error(f"Error updating bridges: {e}")
        with open(summary_file, "a") as sf:
            sf.write(f"Error: {str(e)}\n")
        raise

if __name__ == "__main__":
    update_bridges()