"""Deterministic clinical engine for HAC-Renal AI.

This module implements the four-stage workflow described in the project
requirements document:

  Stage 1  Data collection and completeness gate -> abstain instead of guessing.
  Stage 2  Safety + therapy-appropriateness assessment.
  Stage 3  Deterministic renal/dialysis dose selection (plain Python functions).
  Stage 4  Monitoring and reassessment plan.

The language model is deliberately kept out of this file: every number, band and
decision produced here comes from explicit rules and the drug registry.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
PARENT = os.path.dirname(ROOT)
if PARENT not in sys.path:
    sys.path.insert(0, PARENT)

from tools.crcl_calculator import calculate_crcl  # noqa: F401  (kept for callers)
from data.clinical_data import (
    DRUG_HYPERSENSITIVITY,
    DRUG_INTERACTION_COVERAGE,
    MONITORING_DIALYSIS,
    MONITORING_PLAN,
    REASSESSMENT_TRIGGERS,
    get_interaction,
    get_monitoring_plan,
    get_therapy_rule,
)
from data.clinical_vocabulary import (
    classify_dialysis,
    classify_infection_type,
    classify_meropenem_indication,
)
from data.drug_bounds import check_bounds, declared_bounds
from data.drug_registry import (
    UnsupportedDrugError,
    get_drug_module,
    resolve_drug,
    supported_drugs,
)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
def _normalize(patient_input):
    """Turn loosely-typed caller input into one predictable internal shape."""
    pi = dict(patient_input or {})
    out = {}
    out["drug"] = pi.get("requested_drug") or pi.get("drug")
    out["age"] = pi.get("age_years", pi.get("age"))
    out["weight_kg"] = pi.get("weight_kg", pi.get("weight"))
    out["crcl_ml_min"] = pi.get("crcl_ml_min", pi.get("crcl"))
    out["creatinine"] = pi.get("creatinine")
    out["gender"] = pi.get("gender")
    out["indication"] = pi.get("indication_group", pi.get("indication"))
    out["infusion_strategy"] = pi.get("infusion_strategy", pi.get("infusion"))
    out["infection_type"] = pi.get("infection_type")
    out["allergy_history"] = pi.get("allergy_history", []) or []
    out["concomitant_medications"] = pi.get("concomitant_medications", []) or []
    out["culture_result"] = pi.get("culture_result")
    out["infection_documented"] = pi.get("infection_documented")

    d = pi.get("dialysis", {}) or {}
    status = str(d.get("status", "")).strip().lower()
    if status in ("yes", "y", "true", "1", "on"):
        out["on_dialysis"] = True
        out["dialysis_documented"] = True
    elif status in ("no", "n", "false", "0", "off"):
        out["on_dialysis"] = False
        out["dialysis_documented"] = True
    else:
        out["on_dialysis"] = False
        out["dialysis_documented"] = False

    if out["on_dialysis"]:
        raw_modality = (
            d.get("modality")
            or d.get("modality_reported_by_clinician")
            or d.get("modality_documented_in_source")
        )
        out["cvvhd_flow_rate"] = d.get("flow_rate_l_per_hour")
    else:
        raw_modality = pi.get("dialysis_modality")
        out["cvvhd_flow_rate"] = pi.get("cvvhd_flow_rate")
        if raw_modality:
            # A modality supplied at top level is itself a statement that the
            # patient is dialysed, even when the nested status is absent.
            out["on_dialysis"] = True
            out["dialysis_documented"] = True

    if not out["on_dialysis"] and not out["dialysis_documented"]:
        # "status" may itself carry the modality ("IHD", "on CRRT").
        mero_status, mero_modality = classify_dialysis(status)
        if mero_status == "Yes":
            out["on_dialysis"] = True
            out["dialysis_documented"] = True
            raw_modality = raw_modality or mero_modality

    # Canonicalise towards IHD / CRRT / PD so every downstream layer compares
    # the same three words; an unmappable modality stays None and the
    # completeness gate asks for it instead of guessing a regimen.
    out["dialysis_modality"] = None
    if out["on_dialysis"] and raw_modality:
        _, modality = classify_dialysis(raw_modality)
        out["dialysis_modality"] = modality
    return out


def _as_lower(value):
    return str(value or "").strip().lower()


# ---------------------------------------------------------------------------
# Stage 1 - completeness gate
# ---------------------------------------------------------------------------
def required_missing_fields(n, drug_module, drug_key):
    """Return the fields that must be supplied before a dose may be selected.

    Only fields that would actually force the engine to guess are listed, and
    they are derived from what each drug's rules genuinely consume:
      * every drug needs the dialysis status (renal vs dialysis band);
      * a dialysis modality is needed when the patient is dialysed;
      * a non-dialysis patient needs a CrCl that is either supplied or
        computable from creatinine + gender + weight + age;
      * meropenem needs the indication (all paths) and, off dialysis, the
        infusion strategy;
      * vancomycin needs the infection type off dialysis and is weight-based,
        so age and weight are always required.
    """
    missing = []
    if not n["dialysis_documented"]:
        missing.append("dialysis_status")

    if n["on_dialysis"]:
        if not n["dialysis_modality"]:
            missing.append("dialysis_modality")
    elif n["crcl_ml_min"] is None:
        can_compute_crcl = (
            n["creatinine"] is not None
            and n["gender"] is not None
            and n["weight_kg"] is not None
            and n["age"] is not None
        )
        if not can_compute_crcl:
            missing.append("crcl")

    field = drug_module["indication_field"]
    if field == "indication_group" and not n["indication"]:
        missing.append("indication_group")
    if field == "infection_type" and not n["on_dialysis"] and not n["infection_type"]:
        missing.append("infection_type")

    if (
        drug_module.get("extra_field") == "infusion_strategy"
        and not n["on_dialysis"]
        and not n["infusion_strategy"]
    ):
        missing.append("infusion_strategy")

    if drug_key == "vancomycin":
        if n["age"] is None:
            missing.append("age_years")
        if n["weight_kg"] is None:
            missing.append("weight_kg")

    return missing


def abstention_result(n, drug_module, missing):
    """Build the stage-1 abstention response instead of guessing a dose."""
    result = {
        "decision": "NEEDS_MORE_INFORMATION",
        "drug": drug_module["canonical_name"],
        "missing_fields": missing,
        "dose_calculation_allowed": False,
        "message": "Insufficient data to select a dose safely; no regimen was generated.",
        "required_action": "Provide: %s." % ", ".join(missing),
        "clinical_review_required": True,
    }
    if "crcl" in missing:
        result["decision"] = "BLOCK"
        result["alert_code"] = "MISSING_CRCL"
        result["message"] = "CrCl is required for renal dose selection."
        result["required_action"] = (
            "Provide CrCl (mL/min) or creatinine+gender+weight+age."
        )
    return result


# ---------------------------------------------------------------------------
# Stage 2 - safety layer (generic over the registry, no drug-specific branches)
# ---------------------------------------------------------------------------
def _hypersensitivity_alert(n, drug_key):
    spec = DRUG_HYPERSENSITIVITY.get(drug_key)
    if not spec:
        return None
    for a in n["allergy_history"]:
        substance = _as_lower((a or {}).get("substance"))
        certainty = _as_lower((a or {}).get("certainty"))
        reaction = _as_lower((a or {}).get("reaction"))
        if any(term in substance for term in spec["terms"]):
            if certainty == "confirmed" or "anaphylaxis" in reaction:
                alert = {
                    "decision": "BLOCK",
                    "alert_code": spec["code"],
                    "dose_calculation_allowed": False,
                    "message": spec["message"],
                    "required_action": spec["action"],
                    "source": spec["source"],
                }
                if spec.get("source_note"):
                    alert["source_note"] = spec["source_note"]
                return alert
    return None


def _interaction_alert(n, drug_key):
    """Screen the concomitant medications against the drug's covered interactions.

    Coverage gaps are declared in DRUG_INTERACTION_COVERAGE rather than hidden.
    """
    for m in n["concomitant_medications"]:
        med = _as_lower((m or {}).get("drug"))
        if not med:
            continue
        for code in DRUG_INTERACTION_COVERAGE.get(drug_key, []):
            inter = get_interaction(code)
            if inter and _as_lower(inter["drug"]) in med:
                return {
                    "decision": "HIGH_PRIORITY_INTERACTION_ALERT",
                    "alert_code": code,
                    "dose_calculation_allowed": True,
                    "message": inter["message"],
                    "required_action": inter["action"],
                    "source": inter["source"],
                }
    return None


def safety_check(patient_input):
    """Backwards-compatible helper: return (is_blocked, alert_or_None)."""
    n = _normalize(patient_input)
    drug_key = resolve_drug(n["drug"])
    if drug_key is None:
        return False, None
    alert = _hypersensitivity_alert(n, drug_key) or _interaction_alert(n, drug_key)
    blocked = alert is not None and alert.get("decision") == "BLOCK"
    return blocked, alert


def _therapy_findings(n, drug_key):
    """Stage 2 - is the therapy itself appropriate? Returns advisory rules."""
    findings = []
    infusion = _as_lower(n["infusion_strategy"]).replace(" ", "_")
    modality = _as_lower(n["dialysis_modality"])

    # THER-001 contraindication (also surfaced as a hard BLOCK by the safety layer)
    if _hypersensitivity_alert(n, drug_key):
        findings.append(get_therapy_rule("THER-001"))

    # THER-002 limited evidence for extended-infusion meropenem in meningitis/CF
    if (
        drug_key == "meropenem"
        and classify_meropenem_indication(n["indication"]) == "Meningitis_CF"
        and infusion in ("extended", "extended_infusion")
    ):
        findings.append(get_therapy_rule("THER-002"))

    # THER-003 no validated PD regimen exists in the project sources
    if n["on_dialysis"] and modality in ("pd", "peritoneal dialysis"):
        findings.append(get_therapy_rule("THER-003"))

    # THER-004 empirical until culture/susceptibility is available
    if not n["culture_result"]:
        findings.append(get_therapy_rule("THER-004"))

    # THER-005 infection not documented -> cannot confirm therapy is indicated
    if n["infection_documented"] is False:
        findings.append(get_therapy_rule("THER-005"))

    # THER-006 the isolate is reported resistant to the selected agent itself
    culture = _as_lower(n["culture_result"]) if n.get("culture_result") else ""
    if culture:
        try:
            module = get_drug_module(drug_key)
        except UnsupportedDrugError:
            module = None
        if module is not None:
            names = [_as_lower(module["canonical_name"])]
            names += [_as_lower(alias) for alias in module.get("aliases", [])]
            if any(name in culture for name in names) and any(
                term in culture for term in ("resistant", "resistance",
                                             "nonsusceptible")
            ):
                findings.append(get_therapy_rule("THER-006"))

    return [f for f in findings if f]


# ---------------------------------------------------------------------------
# Stage 4 - monitoring and reassessment
# ---------------------------------------------------------------------------
def monitoring_plan(n, drug_key):
    """Build the monitoring plan from the chosen drug, renal state and modality."""
    plan = {
        "common": list(MONITORING_PLAN.get("common", [])),
        "drug_specific": get_monitoring_plan(drug_key),
        "reassessment_triggers": list(REASSESSMENT_TRIGGERS),
    }
    if n["on_dialysis"]:
        modality = _as_lower(n["dialysis_modality"])
        if "intermittent" in modality or modality in ("ihd", "hd"):
            plan["dialysis_specific"] = list(MONITORING_DIALYSIS.get("IHD", []))
        elif "cv" in modality or "crrt" in modality or "continuous" in modality:
            plan["dialysis_specific"] = list(MONITORING_DIALYSIS.get("CRRT", []))
        elif "peritoneal" in modality or modality == "pd":
            plan["dialysis_specific"] = list(MONITORING_DIALYSIS.get("PD", []))
    return plan


# ---------------------------------------------------------------------------
# Deterministic dose selection
# ---------------------------------------------------------------------------
def _run_dosing_function(drug_key, drug_module, n):
    fn = drug_module["dosing_function"]
    if drug_key == "vancomycin":
        return fn(
            age=n["age"],
            weight_kg=n["weight_kg"],
            crcl_ml_min=n["crcl_ml_min"],
            creatinine=n["creatinine"],
            gender=n["gender"],
            infection_type=n["infection_type"],
            dialysis_modality=n["dialysis_modality"],
        )
    return fn(
        crcl_ml_min=n["crcl_ml_min"],
        age=n["age"],
        weight_kg=n["weight_kg"],
        creatinine=n["creatinine"],
        gender=n["gender"],
        indication_group=n["indication"],
        infusion_strategy=n["infusion_strategy"],
        dialysis_modality=n["dialysis_modality"],
        cvvhd_flow_rate=n["cvvhd_flow_rate"],
        allergy_history=n["allergy_history"],
        concomitant_medications=n["concomitant_medications"],
    )


def unify_dose_schema(result):
    """Expose a single dose/dose_unit pair whichever drug produced the result.

    Meropenem rules return dose/dose_unit; vancomycin rules return dose_mg.
    Callers (and the language model) should not have to know that difference.
    """
    if "dose" not in result and result.get("dose_mg") is not None:
        result["dose"] = result["dose_mg"]
        result["dose_unit"] = "mg"
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def apply_rules(patient_input):
    """Run the full four-stage pipeline and return one structured result dict.

    Order matters clinically: an absolute contraindication or a high-priority
    interaction is actionable on its own, so it is reported before the engine
    complains about other missing fields.
    """
    n = _normalize(patient_input)

    # --- Drug resolution (fail-closed: no silent fallback to another drug) ---
    if not n["drug"]:
        return {
            "decision": "NEEDS_MORE_INFORMATION",
            "missing_fields": ["requested_drug"],
            "dose_calculation_allowed": False,
            "message": "No drug was requested; no regimen was generated.",
            "required_action": "Specify one of: %s." % ", ".join(supported_drugs()),
            "supported_drugs": supported_drugs(),
            "clinical_review_required": True,
        }
    try:
        drug_module = get_drug_module(n["drug"])
    except UnsupportedDrugError as exc:
        return {
            "decision": "UNSUPPORTED_DRUG",
            "dose_calculation_allowed": False,
            "message": str(exc),
            "required_action": "Select one of the supported drugs: %s."
                               % ", ".join(supported_drugs()),
            "supported_drugs": supported_drugs(),
            "clinical_review_required": True,
        }
    drug_key = resolve_drug(n["drug"])

    # --- Stage 2a: safety layer (contraindications and interactions) ---
    safety = _hypersensitivity_alert(n, drug_key) or _interaction_alert(n, drug_key)
    if safety is not None:
        safety.setdefault("drug", drug_module["canonical_name"])
        safety.setdefault("clinical_review_required", True)
        safety["therapy_assessment"] = _therapy_findings(n, drug_key)
        safety["monitoring_plan"] = monitoring_plan(n, drug_key)
        return safety

    # --- Stage 1: completeness gate (abstain instead of guessing) ---
    missing = required_missing_fields(n, drug_module, drug_key)
    if missing:
        return abstention_result(n, drug_module, missing)

    # --- Stage 1b: declared bounds (never extrapolate past a validated range) ---
    bounds = check_bounds(drug_key, n)
    if bounds is not None:
        bounds.setdefault("drug", drug_module["canonical_name"])
        bounds["declared_bounds"] = declared_bounds(drug_key)
        return bounds

    # --- Stage 3: deterministic dosing ---
    try:
        result = _run_dosing_function(drug_key, drug_module, n)
    except ValueError as exc:
        return {
            "decision": "NEEDS_MORE_INFORMATION",
            "drug": drug_module["canonical_name"],
            "dose_calculation_allowed": False,
            "message": "Dose engine rejected the input: %s" % exc,
            "required_action": "Correct the flagged input and re-run.",
            "clinical_review_required": True,
        }

    result = unify_dose_schema(result)
    result.setdefault("drug", drug_module["canonical_name"])
    result.setdefault("clinical_review_required", True)

    # --- Stage 2b + 4: attach assessment and follow-up plan ---
    result["therapy_assessment"] = _therapy_findings(n, drug_key)
    result["monitoring_plan"] = monitoring_plan(n, drug_key)

    _record_classification(n, drug_key, result)

    return result


def _record_classification(n, drug_key, result):
    """Show which source category free-text wording was mapped onto.

    The clinician may write "MRSA bacteraemia"; the source defines bacteraemia
    as a complicated infection. Recording the mapping keeps the decision
    auditable instead of hiding an interpretation inside the tool.
    """
    if drug_key == "vancomycin" and n.get("infection_type"):
        classified = classify_infection_type(n["infection_type"])
        raw = str(n["infection_type"]).strip().lower()
        if classified and raw != classified:
            result["classified_from"] = n["infection_type"]
            result["infection_type"] = classified
    elif drug_key == "meropenem" and n.get("indication"):
        classified = classify_meropenem_indication(n["indication"])
        raw = str(n["indication"]).strip()
        if classified and raw != classified:
            result["classified_from"] = n["indication"]
            result["indication_group"] = classified
