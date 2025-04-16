# openai_batch_poller.py
# Überwacht laufende OpenAI-Batches und speichert Status + .meta-Datei

import os
import json
import time
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logger = logging.getLogger("__main__")
logging.basicConfig(level=logging.INFO)

BATCH_DIR = "batches"
POLL_INTERVAL = 10


def poll_batch_until_done(batch_id: str):
    while True:
        batch = client.batches.retrieve(batch_id)
        logger.info(f"📦 Batch {batch.id} Status: {batch.status}")

        if batch.status in ["completed", "failed", "cancelled"]:
            return batch

        time.sleep(POLL_INTERVAL)


def list_batch_files():
    return [f for f in os.listdir(BATCH_DIR) if f.endswith(".batch_id")]


if __name__ == "__main__":
    batch_files = list_batch_files()
    print(batch_files)
    if not batch_files:
        logger.info("📬 Keine Batch-Dateien zum Überwachen gefunden.")
        exit(0)

    for file in batch_files:
        print(file)
        path = os.path.join(BATCH_DIR, file)
        with open(path, "r") as f:
            batch_id = f.read().strip()

        logger.info(f"👀 Überwache Batch-ID: {batch_id}")
        result = poll_batch_until_done(batch_id)

        # Speichere Status
        status_path = os.path.join(BATCH_DIR, f"{batch_id}_status.json")
        with open(status_path, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Status gespeichert unter: {os.path.basename(status_path)}")

        # Schreibe Meta-Datei für spätere Archivierung
        meta_path = os.path.join(BATCH_DIR, f"{batch_id}.meta")
        with open(meta_path, "w", encoding="utf-8") as f:
            input_file_name = result.input_file_id.replace("file-", "") + ".json"
            f.write(f"{input_file_name}\n")
            f.write(f"{batch_id}_status.json\n")
            f.write(f"{file}\n")  # ursprüngliche .batch_id Datei
        logger.info(f"📜 Meta-Datei geschrieben: {os.path.basename(meta_path)}")

        # Entferne .batch_id Datei
        os.remove(path)
