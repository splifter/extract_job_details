import os
import json
import uuid
import logging
import argparse
from typing import List, Dict
from prompt_loader import load_prompt, render_prompt

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

def submit_batch(batch_items: List[Dict[str, str]], id) -> None:
    batch_id = str(uuid.uuid4())
    json_path = os.path.join(BATCH_DIR, f"{batch_id}.json")

    system_prompt_template = load_prompt('system_prompt_template.txt')
    context = {'id': id}
    system_prompt = render_prompt(system_prompt_template, context)

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
                            "content": f"{system_prompt}"
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


def resend_batch_from_file(json_path: str):
    if not os.path.exists(json_path):
        logger.error(f"❌ Batch-Datei nicht gefunden: {json_path}")
        return

    logger.info(f"📤 Lade vorhandene Batch-Datei hoch: {json_path}")
    with open(json_path, "rb") as f:
        file = client.files.create(file=f, purpose="batch")

    logger.info(f"🚀 Starte Batch mit File-ID: {file.id}")
    batch = client.batches.create(
        input_file_id=file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )

    # Speicher Batch-ID für Poller
    batch_id_path = os.path.join("batches", f"{batch.id}.batch_id")
    with open(batch_id_path, "w") as f:
        f.write(batch.id)

    logger.info(f"✅ Batch neu gestartet mit ID: {batch.id}")
    logger.info(f"💾 Batch-ID gespeichert unter: {batch_id_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OpenAI Batch Submitter")
    parser.add_argument("--resend", type=str, help="Pfad zu einer bestehenden Batch-JSON-Datei")
    args = parser.parse_args()

    if args.resend:
        resend_batch_from_file(args.resend)