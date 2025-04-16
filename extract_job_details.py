import os
import re
import sys
import time
import json
import logging
from typing import Dict, Any, List

import requests
import gspread
from dotenv import load_dotenv
from markdownify import markdownify as md
from oauth2client.service_account import ServiceAccountCredentials
from gspread import Worksheet

from logger_config import setup_logger
from openai_batch_submitter import submit_batch

# === Load Environment Variables ===
load_dotenv()

# === Configuration from .env ===
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "JOB_COLLECTOR")
FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "http://localhost:8191")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
MAX_ROWS = int(os.getenv("MAX_ROWS", 999))

# Field mapping from GPT output to Google Sheet columns
FIELD_MAPPING = {
    "job_title": "titel",
    "job_description": "job_description",
    "company_name": "Arbeitgeber",
    "city": "Ort",
    "country": "Land",
    "responsibilities": "responsibilities",
    "requirements": "requirements",
    "employment_type": "employment_type",
    "seniority_level": "seniority_level",
    "industry": "industry",
    "content_url": "Source",
    "id": "id"
}

# === Logger Setup ===
setup_logger()
logger = logging.getLogger(__name__)

def init_gsheet() -> Worksheet:
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
    )
    gclient = gspread.authorize(creds)
    return gclient.open_by_key(GOOGLE_SHEET_ID).worksheet(SHEET_NAME)

def fetch_markdown(source_url: str) -> str:
    try:
        url = f"https://r.jina.ai/{source_url}"
        response = requests.get(url, headers={"X-Retain-Images": "none", "User-Agent": "Mozilla/5.0"}, timeout=10)
        response.raise_for_status()
        logger.debug(f"Fetched markdown from r.jina.ai for URL: {source_url}")
        return response.text
    except Exception as e:
        logger.warning(f"r.jina.ai failed for {source_url}, trying FlareSolverr: {e}")
        try:
            payload = {"cmd": "request.get", "url": source_url, "maxTimeout": 180000}
            resp = requests.post(f"{FLARESOLVERR_URL}/v1", json=payload, headers={"Content-Type": "application/json"}, timeout=120)
            resp.raise_for_status()
            return md(resp.json().get("solution", {}).get("response", ""))
        except Exception as fe:
            logger.error(f"Both markdown sources failed for {source_url}: {fe}")
            return ""

def get_relevant_rows(sheet: Worksheet) -> List[Dict[str, Any]]:
    all_rows = sheet.get_all_records()
    logger.info(f"🟡 {len(all_rows)} Zeilen im Sheet geladen.")
    return [
        {"row_index": idx, "data": row}
        for idx, row in enumerate(all_rows)
        if row.get("Status") == "neu"
    ]

def process(dry_run: bool = True):
    sheet = init_gsheet()
    rows = get_relevant_rows(sheet)
    batch_items = []
    processed_count = 0

    for item in rows:
        if processed_count >= MAX_ROWS:
            break

        idx = item["row_index"]
        row = item["data"]
        job_id = row["id"]
        logger.info(f"🔄 Vorbereitung ID: {job_id}")

        markdown = row.get("markdown", "").strip() or fetch_markdown(row.get("Source", ""))

        if not markdown:
            logger.warning(f"⚠️ Kein Markdown für {job_id}, übersprungen.")
            continue

        user_prompt = f"Hier ist die Anzeige zur Analyse in Markdown-Format:\n\n{markdown}\n\nNutze dieses Format für deine Antwort:\n\n{{\n  \"id\": \"{job_id}\",\n  \"job_title\": \"\",\n  \"job_description\": \"\",\n  \"company_name\": \"\",\n  \"city\": \"\",\n  \"country\": \"\",\n  \"responsibilities\": \"\",\n  \"requirements\": \"\",\n  \"employment_type\": \"\",\n  \"seniority_level\": \"\",\n  \"industry\": \"\",\n  \"content_url\": \"{row.get('Source', '')}\"\n}}"

        batch_items.append({"custom_id": job_id, "content": user_prompt})
        processed_count += 1

    if dry_run:
        logger.info(f"[DRY-RUN] Würde {len(batch_items)} Elemente in Batch packen.")
    else:
        submit_batch(batch_items)

if __name__ == "__main__":
    dry_run_flag = '--live' not in sys.argv
    process(dry_run=dry_run_flag)
