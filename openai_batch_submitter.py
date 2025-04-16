import os
import json
import uuid
import logging
from typing import List, Dict

from openai import OpenAI
from dotenv import load_dotenv

# === Load Environment Variables ===
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# === Logger Setup ===
logger = logging.getLogger("openai_batch_submitter")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

# === Output directory for batch files ===
BATCH_DIR = "batches"
os.makedirs(BATCH_DIR, exist_ok=True)

def submit_batch(batch_items: List[Dict[str, str]]) -> None:
    batch_id = str(uuid.uuid4())
    json_path = os.path.join(BATCH_DIR, f"{batch_id}.json")

    logger.info(f"📦 Erstelle Batch-Datei: {json_path}")
    with open(json_path, "w", encoding="utf-8") as f:
        for item in batch_items:
            f.write(json.dumps({
                "custom_id": item["custom_id"],
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o"),
                    "temperature": 0.3,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Du arbeitest f\u00fcr ein Headhunter-Unternehmen und extrahierst relevante Informationen aus Jobanzeigen (Markdown). Gib die Infos strukturiert auf Deutsch im JSON-Format zur\u00fcck."
                        },
                        {
                            "role": "user",
                            "content": item["content"]
                        }
                    ]
                }
            }) + "\n")

    try:
        logger.info("📤 Lade Batch-Datei als OpenAI-File hoch...")
        file_obj = client.files.create(file=open(json_path, "rb"), purpose="batch")

        logger.info("🚀 Starte Batch mit File-ID: %s", file_obj.id)
        batch = client.batches.create(
            input_file_id=file_obj.id,
            endpoint="/v1/chat/completions",
            completion_window="24h"
        )

        batch_meta_path = os.path.join(BATCH_DIR, f"{batch.id}.batch_id")
        with open(batch_meta_path, "w") as meta_file:
            meta_file.write(batch.id)
        logger.info(f"✅ Batch erstellt: {batch.id} und gespeichert in {batch_meta_path}")

        # Schreibe Meta-Datei für spätere Archivierung
        meta_path = os.path.join(BATCH_DIR, f"{batch_id}.meta")
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(f"{batch_id}.json")

    except Exception as e:
        logger.error("❌ Fehler beim Erstellen des Batches: %s", str(e))