# HAC-Renal AI — Hackathon Demo Script (3 Minutes)

## Overview
This script outlines a 3-minute presentation flow for the HAC-Renal AI hackathon demo.

---

## Minute 1: The Problem — Renal Dosing Complexity

**What to show:** Open the Streamlit app at `http://localhost:8501`

**Script:**
> "Antibiotic dosing in renal impairment is complex. Different drugs have different renal adjustment tables, dialysis considerations, and safety contraindications. A clinician needs to check CrCl, weight, age, indication, infusion strategy, and dialysis status — all while avoiding dangerous drug interactions and allergies.
>
> HAC-Renal AI automates this with deterministic, source-cited rules. No guessing. No hallucinated doses."

**Action:** Show the empty form. Point out the fields: Age, Weight, Creatinine, Dialysis Status, Allergies, Concomitant Medications, and drug-specific fields (Indication Group, Infusion Strategy for Meropenem; Infection Type for Vancomycin).

---

## Minute 2: The Solution — Demo Mode

**What to show:** Enable Demo Mode and run synthetic test cases.

**Script:**
> "Let me demonstrate with synthetic test cases. First, Meropenem MERO-TC-01 — a patient with confirmed meropenem allergy. The system should BLOCK immediately."

**Action:**
1. Select "Meropenem" in sidebar
2. Enable "Demo Mode"
3. Select "MERO-TC-01: Confirmed Meropenem / Beta-lactam Hypersensitivity"
4. Show the BLOCK result with rule_id `CONFIRMED_HYPERSENSITIVITY`
5. Point out the evidence traceability section with source URL

> "Now MERO-TC-03 — CrCl 18 mL/min, standard indication, short infusion. This should give 500 mg q12h."

**Action:**
1. Select "MERO-TC-03: Renal Dose Adjustment - CrCl 18 mL/min"
2. Show the result: 500 mg IV q12h, rule_id from UCSF table
3. Show the evidence section citing UCSF source

**Then Vancomycin:**
1. Select "Vancomycin" in sidebar
2. Select "VAN-TC-01: Normal Renal Function - Complicated Infection" (CrCl 95, 70kg) → expect 1000 mg q8h (VAN-002)
3. Select "VAN-TC-02: Hemodialysis Patient" → expect loading 20-25 mg/kg then 500 mg post-HD (VAN-020)

---

## Minute 3: Safe Failure & Evidence Traceability

**What to show:** Appropriate abstention when critical data is missing.

**Script:**
> "Most important safety feature: Appropriate Abstention. If critical data is missing, the system refuses to calculate. Let me demonstrate."

**Action:**
1. Switch to manual entry (disable Demo Mode)
2. Leave Serum Creatinine blank (or set to 0)
3. Click "Calculate Dose"
4. Show the error: "Cannot calculate dose safely — Missing critical data: Serum Creatinine (mg/dL) or CrCl (mL/min)"
5. Explain: "The system does NOT guess. It does NOT hallucinate. It abstains."

**Then show evidence traceability:**
1. Fill in valid data (e.g., Meropenem, CrCl 18, Standard, Short Infusion)
2. Click Calculate
3. Show the Evidence & Source Traceability section with quote block
4. Point to the rule_id and clickable source URL

> "Every recommendation cites its rule_id and source URL. Clinicians can verify against UCSF guidelines directly."

---

## Key Talking Points for Judges

| Feature | Demo Evidence |
|---------|--------------|
| **Safe Failure / Appropriate Abstention** | Missing creatinine → error, no dose calculated |
| **Deterministic Rules** | Same input always gives same output |
| **Evidence Traceability** | Every result cites rule_id + source URL |
| **Drug Interaction Detection** | Valproate → HIGH_PRIORITY_INTERACTION_ALERT |
| **Allergy Safety** | Confirmed allergy → BLOCK |
| **Dialysis-Specific Dosing** | IHD/CRRT/PD rows use different tables |
| **No LLM Hallucination Risk** | Python tools do all math; LLM only orchestrates (or deterministic fallback) |

---

## Technical Architecture

```
Streamlit UI → Orchestrator → LangChain AI Agent → Deterministic Python Tools
                                    ↓
                              Falls back to deterministic engine if LLM unavailable
```

Tools: CrCl calculator, Meropenem dosing, Vancomycin dosing, Knowledge base search, Safety rule lookup, Interaction checker.

---

## Files Modified/Created in Sprint 4

- `app.py` — Updated with Safe Failure check, API key input, Vancomycin fields, professional result display
- `orchestrator.py` — Now routes through AI Agent with deterministic fallback
- `agents/ai_tools.py` — LangChain tools wrapping all deterministic functions
- `agents/llm_agent.py` — AI Agent with strict system prompt
- `data/vancomycin_synthetic_cases.json` — 3 Vancomycin test cases
- `tests/test_ai_agent.py` — Test suite for AI Agent
- `.env` — API key configuration template
- `knowledge_base/*.md` — Populated with meropenem, vancomycin, TDM rules
