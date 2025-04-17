# ai_job_enricher.py
# Liest Job-IDs & Parameter aus Google Sheet, generiert Prompts, erstellt OpenAI Batch

import os
import json
import uuid
import logging
import argparse
from typing import List, Dict

import gspread
from dotenv import load_dotenv
from jinja2 import Template
from oauth2client.service_account import ServiceAccountCredentials

# === ENV & Logging ===
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === CONFIG ===
BATCH_DIR = "batches"
PROMPT_SYSTEM_PATH = "prompts/ai_search_system.txt"
PROMPT_USER_TEMPLATE_PATH = "prompts/ai_search_user_template.txt"
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
PROMPT_SHEET = os.getenv("PROMPT_SHEET", "JOB_AI_PROMPTS")

# === FUNCTIONS ===

def init_sheet():
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    client = gspread.authorize(creds)
    return client.open_by_key(GOOGLE_SHEET_ID).worksheet(PROMPT_SHEET)

def load_prompts() -> Dict[str, Template]:
    with open(PROMPT_SYSTEM_PATH, "r", encoding="utf-8") as f:
        system_prompt = Template(f.read())
    with open(PROMPT_USER_TEMPLATE_PATH, "r", encoding="utf-8") as f:
        user_prompt = Template(f.read())
    return {"system": system_prompt, "user": user_prompt}

def build_batch_items(rows: List[Dict], templates: Dict[str, Template]) -> List[Dict]:
    items = []
    for row in rows:
        try:
            custom_id = row.get("id") or str(uuid.uuid4())
            user_content = templates["user"].render(**row)
            system_content = templates["system"].render(**row)

            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_content},
            ]

            items.append({
                "custom_id": custom_id,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gpt-4o",
                    "temperature": 0.2,
                    "messages": messages
                }
            })
        except Exception as e:
            logger.warning(f"⚠️ Fehler bei Zeile {row.get('id')}: {e}")
    return items

def save_batch_file(batch_items: List[Dict], filename: str) -> str:
    if not os.path.exists(BATCH_DIR):
        os.makedirs(BATCH_DIR)
    path = os.path.join(BATCH_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(batch_items, f, ensure_ascii=False, indent=2)
    logger.info(f"💾 Batch gespeichert: {path}")
    return path

def main(dry_run=False, retry_path=None):
    if retry_path:
        logger.info(f"🔁 Wiederhole Batch von Datei: {retry_path}")
        with open(retry_path, "r", encoding="utf-8") as f:
            batch_items = json.load(f)
    else:
        sheet = init_sheet()
        rows = sheet.get_all_records()
        templates = load_prompts()
        batch_items = build_batch_items(rows, templates)

    if not batch_items:
        logger.warning("⚠️ Keine gültigen Batch-Einträge vorhanden.")
        return

    batch_filename = f"{uuid.uuid4()}.json"
    batch_path = save_batch_file(batch_items, batch_filename)

    if not dry_run:
        from openai_batch_submitter import submit_batch  # Dynamisch importieren
        submit_batch(batch_items, json_path=batch_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Batch wirklich abschicken")
    parser.add_argument("--retry", type=str, help="Pfad zu existierender JSON-Datei")
    args = parser.parse_args()

    main(dry_run=not args.live, retry_path=args.retry)
