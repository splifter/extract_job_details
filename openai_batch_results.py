# openai_batch_results.py
# Verarbeitet lokale Batch-Ausgabe (.jsonl) und schreibt Daten ins Google Sheet

import os
import json
import logging
import re
import shutil
import zipfile
from typing import Dict, Any

import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from gspread import Worksheet

# === Load environment ===
load_dotenv()

# === Logging ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Environment Config ===
BATCH_DIR = "batches"
ARCHIVE_DIR = os.path.join(BATCH_DIR, "archive")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
SHEET_NAME = os.getenv("SHEET_NAME", "JOB_COLLECTOR")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")

# === Field Mapping ===
FIELD_MAPPING = {
    "job_description": "job_description",
    "responsibilities": "responsibilities",
    "requirements": "requirements",
    "employment_type": "employment_type",
    "seniority_level": "seniority_level",
    "industry": "industry",
    "id": "id"
}

def init_gsheet() -> Worksheet:
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        GOOGLE_SERVICE_ACCOUNT_FILE,
        ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    )
    gclient = gspread.authorize(creds)
    return gclient.open_by_key(GOOGLE_SHEET_ID).worksheet(SHEET_NAME)

def load_jsonl(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Fehler beim Parsen der Zeile in {filepath}: {e}")

def extract_json_from_content(content: str) -> Dict:
    try:
        match = re.search(r"```(?:json)?\n(.*?)\n```", content, re.DOTALL)
        if match:
            content = match.group(1)
        content = content.strip()
        return json.loads(content)
    except Exception as e:
        logger.warning(f"⚠️ Fehler beim Parsen der GPT-Antwort: {e}")
        return {}

def flatten_value(value: Any) -> str:
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            label = k.upper().replace("_", " ")
            if isinstance(v, list):
                parts.append(f"{label}:")
                parts.extend(map(str, v))
            else:
                parts.append(f"{label}: {v}")
        return "\n\n".join(parts)
    elif isinstance(value, list):
        return "\n".join(map(str, value))
    return str(value)

def update_sheet_with_results(sheet: Worksheet, results_file: str):
    logger.info(f"📥 Verarbeite Datei: {results_file}")
    results = list(load_jsonl(results_file))
    all_rows = sheet.get_all_records()

    for result in results:
        custom_id = result.get("custom_id")
        response = result.get("response", {})
        body = response.get("body", {})
        choices = body.get("choices", [])

        if not choices:
            logger.warning(f"⚠️ Keine GPT-Antwort für ID: {custom_id}")
            continue

        content = choices[0].get("message", {}).get("content", "")
        if not content.strip():
            logger.warning(f"⚠️ Leere GPT-Antwort für ID: {custom_id}")
            continue

        json_data = extract_json_from_content(content)
        if not json_data:
            logger.warning(f"⚠️ Konnte JSON aus Antwort nicht parsen (ID: {custom_id})")
            continue

        for idx, row in enumerate(all_rows):
            if str(row.get("id")) == custom_id:
                logger.info(f"🔄 Aktualisiere Zeile {idx + 2} für ID {custom_id}")
                update_fields(sheet, idx, json_data)
                update_status(sheet, idx, "AI reviewed")
                break

def update_fields(sheet: Worksheet, row_index: int, field_data: Dict[str, str]) -> None:
    for key, sheet_col in FIELD_MAPPING.items():
        if key in field_data:
            value = flatten_value(field_data[key])
            try:
                cell = sheet.find(sheet_col)
                sheet.update_cell(row_index + 2, cell.col, value)
            except Exception as e:
                logger.warning(f"⚠️ Fehler beim Aktualisieren der Zelle '{sheet_col}' in Zeile {row_index + 2}: {e}")

def update_status(sheet: Worksheet, row_index: int, status: str):
    try:
        status_col = sheet.find("Status").col
        sheet.update_cell(row_index + 2, status_col, status)
    except Exception as e:
        logger.error(f"❌ Fehler beim Setzen des Status in Zeile {row_index + 2}: {e}")

def archive_batch_group(batch_id: str):
    meta_file = os.path.join(BATCH_DIR, f"{batch_id}.meta")
    if not os.path.exists(meta_file):
        logger.warning(f"⚠️ Keine .meta-Datei gefunden für {batch_id}, überspringe Archivierung.")
        return

    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)

    zip_path = os.path.join(ARCHIVE_DIR, f"{batch_id}.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        with open(meta_file, "r") as meta:
            for fname in meta:
                fname = fname.strip()
                full_path = os.path.join(BATCH_DIR, fname)
                if os.path.exists(full_path):
                    zipf.write(full_path, arcname=fname)
                    os.remove(full_path)
                    logger.info(f"📁 Archiviert: {fname}")
    os.remove(meta_file)
    logger.info(f"📦 Batch-Dateien gepackt nach: {zip_path}")

def archive_file(filepath: str):
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
    archive_path = shutil.make_archive(filepath, 'zip', root_dir=os.path.dirname(filepath), base_dir=os.path.basename(filepath))
    shutil.move(archive_path, os.path.join(ARCHIVE_DIR, os.path.basename(archive_path)))
    os.remove(filepath)
    logger.info(f"📦 Archiviert und entfernt: {filepath}")

if __name__ == "__main__":
    output_file = None
    batch_id = None

    for fname in os.listdir(BATCH_DIR):
        if fname.endswith(".jsonl"):
            output_file = os.path.join(BATCH_DIR, fname)
            batch_id = fname.split(".")[0].replace("file-", "batch_")
            break

    if not output_file:
        logger.info("📭 Keine Batch-Ausgabedateien gefunden.")
        exit()

    sheet = init_gsheet()
    update_sheet_with_results(sheet, output_file)
    archive_file(output_file)
    if batch_id:
        archive_batch_group(batch_id)
    logger.info("✅ Verarbeitung abgeschlossen.")
