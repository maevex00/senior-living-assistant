# Senior Living Placement Assistant
### AI-Powered Workflow Automation for Assisted Living Advisors
**Simon Business School — MSAIB Capstone | Built for Assisted Living Locators**

🔗 **[Live Demo](https://maevex00-senior-living-assistant-app-j7p7i1.streamlit.app/)** — Toggle "Demo Mode" in the sidebar, no credentials needed.

---

## Overview

The **Senior Living Placement Assistant** is a Streamlit application that automates the senior living placement workflow used by Assisted Living Locators (ALL).

Advisors previously spent **30+ minutes** manually reviewing consultation calls and searching for communities. This tool reduces that to **3–4 minutes** through an end-to-end AI pipeline:

| Step | Technology | What it does |
|------|-----------|--------------|
| Audio transcription | OpenAI Whisper | Converts consultation recordings to text |
| Preference extraction | GPT-4o (JSON mode) | Pulls structured client data from raw transcript |
| Community matching | pandas + Google Sheets | Filters by care level, budget, enhanced/enriched |
| Distance ranking | pgeocode + geopy | Ranks by priority tier, then proximity |
| Match explanations | GPT-4o-mini (batched) | One-sentence AI rationale per community |
| Export | CSV | Priority-tiered download for advisor use |

**Measured business impact:** 88% reduction in advisor processing time, enabling ~70% more placements per advisor per day.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    Streamlit Frontend                        │
└───────────┬──────────────────────────────────────────────────┘
            │
  ┌─────────▼─────────┐
  │  Audio Upload      │  MP3 / M4A / WAV / MP4
  └─────────┬─────────┘
            │
  ┌─────────▼─────────┐
  │  OpenAI Whisper   │  Speech-to-text transcription
  └─────────┬─────────┘
            │
  ┌─────────▼─────────┐
  │  GPT-4o           │  Structured preference extraction
  │  (JSON mode)      │  → name, care level, budget, location…
  └─────────┬─────────┘
            │
  ┌─────────▼─────────┐    ┌──────────────────────┐
  │  Filter & Rank    │◄───│  Google Sheets DB    │
  │  Engine           │    │  (or Demo CSV)       │
  └─────────┬─────────┘    └──────────────────────┘
            │
  ┌─────────▼─────────┐    ┌──────────────────────┐
  │  Geo-distance     │◄───│  pgeocode (offline)  │
  │  Scoring          │    │  + geopy (city names)│
  └─────────┬─────────┘    └──────────────────────┘
            │
  ┌─────────▼─────────┐
  │  GPT-4o-mini      │  Batch explanations (1 API call)
  └─────────┬─────────┘
            │
  ┌─────────▼─────────┐
  │  Ranked Results   │  Priority-tiered display + CSV export
  └───────────────────┘
```

---

## Features

### 1. Audio Upload & Transcription
- Supports MP3, M4A, WAV, MP4
- Uses OpenAI Whisper API for accurate speech-to-text

### 2. AI Preference Extraction
Extracts structured data using GPT-4o in JSON mode (no markdown parsing needed):
- Patient name, age, care level, cognitive status
- Monthly budget, preferred locations, move-in window
- Enhanced / enriched care requirements
- Pet-friendly, tour availability, contact info

### 3. Community Database Matching
Pulls from a private Google Sheet and filters by:
- Care level (Assisted Living, Memory Care, Independent Living)
- Enhanced / enriched availability
- Budget ceiling
- Placement partnership or contracted rates

### 4. Priority Tier Ranking
Communities ranked into three tiers, sorted by distance within each tier:

| Tier | Criteria |
|------|----------|
| 🥇 Priority 1 | Contracted rates |
| 🥈 Priority 2 | Placement partners (no contract) |
| 🥉 Priority 3 | Other communities |

### 5. AI Match Explanations
All match explanations are generated in **one batched API call** (GPT-4o-mini), then cached — no per-card API latency.

### 6. CSV Export
Download Priority 1, Priority 2, or all matching communities.

---

## Demo Mode

The app ships with a built-in demo that requires **no credentials**:

1. Toggle **🎮 Demo Mode** in the sidebar
2. Click **🚀 Launch Demo**
3. The app loads a sample consultation transcript and 15 Rochester NY communities

This demonstrates the full ranking and results pipeline without needing a Google Sheets connection or audio file.

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/senior-living-assistant.git
cd senior-living-assistant
```

### 2. Create a virtual environment

```bash
python -m venv env
source env/bin/activate       # macOS / Linux
env\Scripts\activate          # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure secrets

Create `.streamlit/secrets.toml`:

```toml
# OpenAI
OPENAI_API_KEY = "sk-..."

# Google Cloud Service Account
[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."
client_id = "..."
token_uri = "https://oauth2.googleapis.com/token"
```

> **Note:** Secrets are only required for the live Google Sheets integration. Demo Mode works without any secrets.

### 5. Run the app

```bash
streamlit run app.py
```

Opens at `http://localhost:8501`

---

## Deploying to Streamlit Cloud

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and connect the repo
3. Set `app_final.py` as the entry point
4. Add secrets in the Streamlit Cloud dashboard (Settings → Secrets)

---

## Project Structure

```
senior_living_assistant/
├── app.py                    # Streamlit entry point (UI only)
├── requirements.txt          # Runtime dependencies
├── requirements-dev.txt      # Dev dependencies (pytest)
├── README.md
├── src/
│   ├── ai_pipeline.py        # Whisper transcription, GPT-4o extraction, batch explanations
│   ├── geo.py                # pgeocode + geopy geocoding utilities
│   ├── ranking.py            # Community filtering and priority-tier ranking
│   └── data_loader.py        # Google Sheets loader + demo fixtures
└── tests/
    ├── test_ranking.py        # 15 unit tests for filtering & ranking logic
    ├── test_geo.py            # 9 unit tests for geocoding utilities
    └── test_ai_pipeline.py    # 12 unit tests for AI pipeline (mocked OpenAI)
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | Streamlit |
| AI — Transcription | OpenAI Whisper |
| AI — Extraction | GPT-4o (JSON mode) |
| AI — Explanations | GPT-4o-mini (batched) |
| Database | Google Sheets via gspread |
| Auth | google-auth (Service Account) |
| Geolocation | pgeocode (offline) + geopy |
| Data processing | Python, pandas |

---

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

36 tests across ranking logic, geocoding utilities, and AI pipeline (mocked).

---

## Future Enhancements

- CRM integration (Salesforce / HubSpot) for automatic record creation
- Auto-email recommendations to advisors after ranking
- Multi-region community database support
- Map visualization of matched communities

---

