# HAC-Renal AI — React + 3D Edition

This package keeps the original Python backend files **unchanged** (`rules_engine.py`, `orchestrator.py`, `evidence_retriever.py`, `followup_engine.py`, `agents/`, `tools/`, `data/`). It adds `api_bridge.py` as a thin HTTP adapter and `frontend/` as a new React + Three.js UI. The old Streamlit UI is still available.

## Windows / VS Code quick start

Install **standard Python 3.12 (64-bit)** and **Node.js 20+**. Use two terminals, opened in the folder containing `api_bridge.py` and `frontend/`.

### Terminal 1 — Python API

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-api.txt
python -m uvicorn api_bridge:app --reload --host 127.0.0.1 --port 8000
```

Test: http://127.0.0.1:8000/api/health

### Terminal 2 — React

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173

### Build production frontend

```powershell
cd frontend
npm run build
```

## Important notes

- This is a **research/demo clinical interface**. Clinical decisions must be reviewed by a qualified clinician. Use synthetic/de-identified test cases only.
- The dashboard displays **actual saved case counts**. The design concept's 24 patients / 12 antibiotics / dose recommendations were illustrative, not copied into the application.
- **Patient identity database, QR ID and prescription OCR** are *not* implemented by the original backend. The UI labels the scanner as planned/disabled rather than faking functionality.
- AI Copilot requires a configured API key in Settings. The key is kept only in React memory and sent to the local adapter for the request; it is not written to case files.
- Existing saved cases remain in `cases/`. The original Streamlit app still runs with `python -m streamlit run app.py`.
- This local prototype API has no authentication. **Do not deploy it publicly or enter real patient information** without proper security, access control and clinical validation.
