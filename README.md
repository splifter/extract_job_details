# Extract Job Details - AI-Powered Job Post Analysis

This project automates the extraction of structured job details from job posting URLs using OpenAI's batch API, Markdown parsing, and Google Sheets for tracking. The goal is to analyze a large number of job postings efficiently and maintain a clean, scalable workflow.

## Features

- Fetches job posting content as Markdown using Jina or FlareSolverr
- Uses OpenAI GPT (via batch API) to extract structured job information
- Stores and tracks job data in a Google Sheet
- Supports both dry-run and live execution modes
- Archives processed batches
- Centralized, template-based system and user prompts

---

## Prerequisites

- Python 3.10+
- Google Service Account credentials (for Sheets access)
- OpenAI API Key
- `gspread`, `openai`, `jinja2`, `requests`, `dotenv`, etc.
- `.env` file with the following entries:

```
GOOGLE_SHEET_ID=your-sheet-id
SHEET_NAME=JOB_COLLECTOR
GOOGLE_SERVICE_ACCOUNT_FILE=credentials.json
OPENAI_API_KEY=your-openai-api-key
OPENAI_MODEL=gpt-4o
FLARESOLVERR_URL=http://localhost:8191
```

---

## File Structure

```text
.
├── extract_job_details.py          # Main script for triggering batch creation
├── openai_batch_submitter.py       # Submits batch jobs to OpenAI
├── openai_batch_poller.py          # Polls and finalizes batches
├── openai_batch_fetcher.py         # Fetches batch results from OpenAI
├── openai_batch_results.py         # Parses results and updates the Google Sheet
├── prompt_loader.py                # Loads and renders prompt templates
├── prompts/
│   ├── prompt_system.txt           # System message template
│   └── prompt_user_template.txt    # User message template
├── batches/                        # Contains batch input/output/status/meta files
│   └── archive/                    # Archived and compressed batches
└── .env                            # Environment configuration
```

---

## Usage

### 1. Dry Run (Test Mode)

```bash
python extract_job_details.py
```

### 2. Live Run (Create Batch Job)

```bash
python extract_job_details.py --live
```

### 3. Poll for Completion

```bash
python openai_batch_poller.py
```

### 4. Fetch Batch Result

```bash
python openai_batch_fetcher.py
```

### 5. Apply Results to Google Sheet

```bash
python openai_batch_results.py
```

---

## Centralized Prompt Management

Prompts are defined in the `prompts/` folder:

- `prompt_system.txt` is the system message for the GPT chat
- `prompt_user_template.txt` contains a Jinja2-style template with `{{ job_id }}` and `{{ markdown }}` placeholders

You can easily update the prompt logic without changing any Python code.

---

## Output Format

The GPT response should be in this JSON structure:

```json
{
  "id": "10001-1001234567-S",
  "job_title": "...",
  "job_description": "...",
  "company_name": "...",
  "city": "...",
  "country": "...",
  "responsibilities": ["..."],
  "requirements": ["..."],
  "employment_type": "...",
  "seniority_level": "...",
  "industry": "...",
  "content_url": "https://..."
}
```

---

## License

MIT License

---

## Maintainer

@splifter

---

## Roadmap Ideas

- Schedule full run as cron job or GitHub Action
- Support retries for failed markdown fetches
- Integrate logging UI for processed entries
- Add CLI progress visualization (e.g., tqdm)

