import os
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

logger = logging.getLogger("__main__")
logging.basicConfig(level=logging.INFO)

BATCH_DIR = "batches"

for fname in os.listdir(BATCH_DIR):
    if fname.endswith("_status.json"):
        with open(os.path.join(BATCH_DIR, fname), "r", encoding="utf-8") as f:
            status = json.load(f)

        if status.get("output_file_id"):
            file_id = status["output_file_id"]
            batch_id = status["id"]
            logger.info(f"📄 Lade Ergebnisse aus File-ID: {file_id}")
            contents = client.files.content(file_id)
            output_path = os.path.join(BATCH_DIR, f"{batch_id}.jsonl")
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(contents.text)
            logger.info(f"📄 Ergebnisse gespeichert unter: {output_path}")
        else:
            logger.warning(f"Keine Ergebnisse vorhanden in {fname}")