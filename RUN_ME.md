# HAC-Renal AI — Premium Frontend

## Requirements
Python 3.11+ recommended; Windows/macOS/Linux; internet connection for LLM calls and Google Fonts.

## Windows — quick start
1. Extract the ZIP.
2. Open a terminal in the `HAC-Renal-AI-Premium` folder.
3. Run:

```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

4. Open the local URL shown in your terminal (usually `http://localhost:8501`).

## macOS / Linux
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## LLM connection (optional)
Enter the API key in the left sidebar. You can also copy `.env.example` to `.env` and fill `LLM_API_KEY`. Do not commit `.env` to source control. The deterministic medication review works without any API key.

## Original application preserved
```bash
streamlit run legacy_app.py
```
This is the original interface including detailed follow-up event recording.

## What's new
- Premium responsive clinical dashboard with kidney illustration and dark teal visual identity.
- Dedicated medication review, AI copilot, case timeline and safety pages.
- Original rules engine, evidence retrieval, LLM and case persistence preserved.
- ZIP intentionally excludes `.env`, `.git`, `.venv`, credentials and local caches.

## Important limits
This is a frontend redesign, not clinical validation. Patient ID / longitudinal patient database, image prescription OCR, user authentication and production data security are **not implemented**. Existing saved case records may be demo data. Do not use identifiable real patient data or rely on outputs for prescribing.
