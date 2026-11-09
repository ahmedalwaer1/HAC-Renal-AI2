"""Deterministic clinical follow-up engine (stage 4).

A follow-up system has to do four things the monitoring plan alone cannot:

  1. keep a patient case alive across encounters,
  2. accept a structured follow-up event (new creatinine, drug level, culture,
     clinical response, toxicity, new medication, time-out),
  3. re-run the *same* deterministic pipeline on the updated state, and
  4. compare the new regimen with the previous one and report what changed.

No language model is involved here: ``record_event`` merges the event into the
stored patient state, calls ``apply_rules`` again and diffs the regimens.
"""
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from rules_engine import apply_rules
from data.drug_registry import resolve_drug
from data.followup_rules import (
    get_rule_for_event,
    get_tdm_target,
    next_due_items,
)

# قابلة للضبط عبر متغير بيئة حتى يُركَّب Volume دائم على Railway بدل الملفات
# المؤقتة في الحاوية. القيمة الافتراضية تبقى مجلد cases المحلي كما هي.
CASES_DIR = os.environ.get("HAC_CASES_DIR") or os.path.join(ROOT, "cases")

REGIMEN_FIELDS = (
    "dose",
    "dose_unit",
    "dose_mg_per_kg",
    "route",
    "frequency",
    "rule_id",
    "source_rule",
)

# Fields a follow-up event may write into the stored patient state.
_DIALYSIS_MODALITIES = ("IHD", "HD", "CRRT", "CVVHD", "CVVH", "CVVHDF", "PD")


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------
def merge_patient_input(base, updates):
    """Merge new fields into a stored patient state.

    ``dialysis`` merges key by key, and medication/allergy lists extend rather
    than overwrite, because that is how a follow-up entry is written in practice.
    """
    merged = dict(base or {})
    for key, value in (updates or {}).items():
        if value in (None, "", [], {}):
            continue
        if key == "dialysis" and isinstance(value, dict):
            dialysis = dict(merged.get("dialysis") or {})
            dialysis.update({k: v for k, v in value.items() if v not in (None, "")})
            merged["dialysis"] = dialysis
        elif key in ("concomitant_medications", "allergy_history") and isinstance(value, list):
            merged[key] = list(merged.get(key) or []) + value
        else:
            merged[key] = value
    return merged


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _drug_key_of(patient):
    return resolve_drug((patient or {}).get("requested_drug") or (patient or {}).get("drug"))


def _on_dialysis(patient):
    dialysis = (patient or {}).get("dialysis") or {}
    if str(dialysis.get("status", "")).strip().lower() == "yes":
        return True
    return bool((patient or {}).get("dialysis_modality") or dialysis.get("modality"))


def _is_serious(patient):
    return str((patient or {}).get("infection_type") or "").strip().lower() == "complicated"


def regimen_of(result):
    """Reduce an engine result to the regimen fields that a follow-up compares."""
    result = result or {}
    regimen = {f: result[f] for f in REGIMEN_FIELDS if result.get(f) is not None}
    regimen["decision"] = result.get("decision")
    return regimen


def compare_regimens(previous, current):
    """Diff two regimens field by field."""
    fields = sorted(set(previous) | set(current))
    diffs = [
        {"field": f, "before": previous.get(f), "after": current.get(f)}
        for f in fields
        if previous.get(f) != current.get(f)
    ]
    return {"changed": bool(diffs), "fields": diffs,
            "before": previous, "after": current}


# ---------------------------------------------------------------------------
# Event -> patient-state translation
# ---------------------------------------------------------------------------
def _event_to_patient_updates(event_type, data):
    data = data or {}
    if event_type == "renal_function":
        updates = {}
        for field in ("creatinine", "crcl_ml_min", "weight_kg", "age_years"):
            if data.get(field) is not None:
                updates[field] = data[field]
        return updates

    if event_type == "dialysis_session":
        dialysis = {"status": "Yes"}
        if data.get("modality"):
            dialysis["modality"] = data["modality"]
        updates = {"dialysis": dialysis}
        if data.get("flow_rate_l_per_hour") is not None:
            updates["dialysis"]["flow_rate_l_per_hour"] = data["flow_rate_l_per_hour"]
        return updates

    if event_type == "microbiology":
        result = data.get("culture_result") or data.get("result")
        updates = {"culture_result": result} if result else {}
        if data.get("infection_documented") is not None:
            updates["infection_documented"] = data["infection_documented"]
        return updates

    if event_type == "medication_change":
        meds = [{"drug": m} for m in (data.get("medications") or []) if m]
        return {"concomitant_medications": meds} if meds else {}

    if event_type == "adverse_effect":
        if data.get("creatinine") is not None:
            return {"creatinine": data["creatinine"]}
        return {}

    return {}


# ---------------------------------------------------------------------------
# Therapeutic drug monitoring interpretation
# ---------------------------------------------------------------------------
def _is_quantitative_target(target):
    """True when a declared TDM target is a numeric, directly comparable threshold.

    Only concentration targets (mg/L) and exposure targets (mg*h/L) can be
    compared against a recorded level. A pharmacodynamic target expressed in
    % of the dosing interval (e.g. beta-lactam fT>MIC) is not a level threshold.
    """
    if not target:
        return False
    unit = str(target.get("unit") or "").lower()
    if "mg/l" not in unit and "mg*h/l" not in unit:
        return False
    # تعريض (low/high) مباشرة، أو نطاق (serious_range/non_serious_range)
    if target.get("low") is not None:
        return True
    return bool(target.get("serious_range") and target.get("non_serious_range"))


def interpret_level(patient, data):
    """Classify a recorded drug level against the case's TDM target."""
    drug_key = _drug_key_of(patient) or "vancomycin"
    targets = get_tdm_target(drug_key)
    if not targets:
        return {"status": "NO_TARGET_DEFINED",
                "message": "No TDM target is defined for this drug in the project.",
                "source": None}

    primary = targets.get("primary") or {}
    value = (data or {}).get("value")
    if value is None:
        return {"status": "NO_VALUE", "metric": primary.get("metric"),
                "message": "No level value was recorded.", "source": primary.get("source")}

    level_type = str((data or {}).get("level_type") or "auc").strip().lower()

    trough = targets.get("trough_context") or {}

    # المقارنة مدفوعة بالبيانات وليست مرتبطة باسم الدواء: يجرى المقارنة فقط
    # عندما يكون الهدف المُصرَّح رقماً قابلاً للمقارنة في نفس وحدات المستوى
    # (mg/L) أو بوحدة تعرض (mg*h/L مثل AUC24/MIC). أهداف الأمداء الدوائية
    # مثل fT>MIC (نسبة مئوية) ليس لها عتبة مستوى رقمية -> رفض صريح (fail-closed).
    if level_type == "trough" and _is_quantitative_target(trough):
        selected, use_serious_range = trough, True
    elif _is_quantitative_target(primary):
        selected, use_serious_range = primary, False
    else:
        return {
            "status": "NUMERIC_TARGET_UNAVAILABLE",
            "metric": primary.get("metric"),
            "target_label": "%s-%s %s" % (primary.get("low"), primary.get("high"),
                                          primary.get("unit")),
            "note": primary.get("note"),
            "source": primary.get("source"),
            "message": "A pharmacodynamic target exists for this drug but the project "
                       "defines no numeric level threshold; interpret against the local "
                       "protocol.",
        }

    try:
        value = float(value)
    except (TypeError, ValueError):
        return {"status": "INVALID_VALUE", "message": "The level value is not numeric.",
                "source": primary.get("source")}

    serious = _is_serious(patient)

    if use_serious_range:
        low, high = (trough.get("serious_range") if serious
                     else trough.get("non_serious_range"))
        metric = trough.get("metric")
    else:
        low, high = selected.get("low"), selected.get("high")
        metric = selected.get("metric")
    unit = selected.get("unit")
    note = selected.get("note")
    source = selected.get("source")

    if value < low:
        status, direction = "BELOW_TARGET", "increase exposure"
    elif value > high:
        status, direction = "ABOVE_TARGET", "reduce exposure"
    else:
        status, direction = "WITHIN_TARGET", "maintain the current dose"

    return {
        "level_type": level_type,
        "metric": metric,
        "unit": unit,
        "value": value,
        "target_low": low,
        "target_high": high,
        "target_label": "%s-%s %s" % (low, high, unit),
        "serious_infection": serious,
        "status": status,
        "direction": direction,
        "note": note,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Case lifecycle
# ---------------------------------------------------------------------------
def new_case_id():
    return "CASE-" + datetime.now().strftime("%Y%m%d-%H%M%S")


def open_case(patient_input, label=None, case_id=None):
    """Create a new case and compute its baseline regimen."""
    patient = dict(patient_input or {})
    result = apply_rules(patient)
    drug_key = _drug_key_of(patient)
    now = _now()
    return {
        "case_id": case_id or new_case_id(),
        "label": label or "",
        "opened_at": now,
        "updated_at": now,
        "patient": patient,
        "drug": drug_key,
        "baseline_result": result,
        "current_result": result,
        "timeline": [{
            "at": now,
            "event": "baseline",
            "note": "Initial regimen",
            "decision": result.get("decision"),
            "regimen": regimen_of(result),
            "result": result,
            "reassessment": None,
        }],
        "next_due": next_due_items(drug_key, _on_dialysis(patient)),
    }


def record_event(case, event):
    """Apply one follow-up event to a case and return the re-assessment.

    The case dictionary is updated in place (patient state, current result,
    timeline, next-due list). Persist it with :func:`save_case`.
    """
    event = dict(event or {})
    event_type = event.get("type")
    data = event.get("data") or {}

    rule = get_rule_for_event(event_type)
    if rule is None:
        raise ValueError("Unknown follow-up event type: %s" % event_type)

    previous_regimen = regimen_of(case.get("current_result"))
    updates = _event_to_patient_updates(event_type, data)
    patient = merge_patient_input(case.get("patient"), updates)

    # A newly measured creatinine supersedes a previously supplied CrCl: keeping
    # the old CrCl would hide the renal change the follow-up is meant to catch.
    crcl_superseded = (
        event_type == "renal_function"
        and data.get("creatinine") is not None
        and data.get("crcl_ml_min") is None
        and patient.get("crcl_ml_min") is not None
    )
    if crcl_superseded:
        patient.pop("crcl_ml_min", None)

    new_result = apply_rules(patient)
    new_regimen = regimen_of(new_result)

    reassessment = {
        "at": _now(),
        "rule_id": rule["rule_id"],
        "severity": rule["severity"],
        "event": event_type,
        "trigger": rule["trigger"],
        "action": rule["action"],
        "source": rule["source"],
        "note": event.get("note"),
        "regimen_change": compare_regimens(previous_regimen, new_regimen),
    }
    if crcl_superseded:
        reassessment["crcl_recomputed_from_creatinine"] = True

    if event_type == "drug_level":
        reassessment["level_assessment"] = interpret_level(patient, data)

    if event_type == "clinical_response":
        response = str(data.get("response") or "").strip().lower()
        reassessment["response"] = response
        if response in ("improving", "stable"):
            reassessment["severity"] = "CONTINUE"
            reassessment["action"] = ("Continue the current regimen and the routine "
                                      "monitoring schedule.")

    if event_type == "adverse_effect":
        reassessment["effect"] = data.get("effect")
        reassessment["hold_automated_recommendation"] = True

    if event_type == "duration_review":
        reassessment["day"] = data.get("day")

    if event_type == "microbiology":
        findings = [f for f in (new_result.get("therapy_assessment") or []) if f]
        has_empirical_flag = any(f.get("rule_id") == "THER-004" for f in findings)
        reassessment["empirical_flag_cleared"] = (
            bool(patient.get("culture_result")) and not has_empirical_flag
        )

    reassessment.setdefault(
        "requires_pharmacist_action", reassessment["severity"] != "CONTINUE"
    )

    case["patient"] = patient
    case["current_result"] = new_result
    case["updated_at"] = reassessment["at"]
    case["next_due"] = next_due_items(_drug_key_of(patient), _on_dialysis(patient))
    case.setdefault("timeline", []).append({
        "at": reassessment["at"],
        "event": event_type,
        "note": event.get("note"),
        "decision": new_result.get("decision"),
        "regimen": new_regimen,
        "result": new_result,
        "reassessment": reassessment,
    })
    return reassessment


# ---------------------------------------------------------------------------
# Persistence (one JSON file per case)
# ---------------------------------------------------------------------------
def _case_path(case_id):
    return os.path.join(CASES_DIR, "%s.json" % case_id)


def save_case(case):
    os.makedirs(CASES_DIR, exist_ok=True)
    path = _case_path(case["case_id"])
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(case, handle, ensure_ascii=False, indent=2, default=str)
    return path


def load_case(case_id):
    path = _case_path(case_id)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def list_cases():
    if not os.path.isdir(CASES_DIR):
        return []
    summaries = []
    for name in sorted(os.listdir(CASES_DIR), reverse=True):
        if not name.endswith(".json"):
            continue
        case = load_case(name[:-5])
        if not case:
            continue
        summaries.append({
            "case_id": case.get("case_id"),
            "label": case.get("label") or "",
            "drug": case.get("drug"),
            "updated_at": case.get("updated_at"),
            "decision": (case.get("current_result") or {}).get("decision"),
            "events": max(len(case.get("timeline") or []) - 1, 0),
        })
    return summaries


def delete_case(case_id):
    path = _case_path(case_id)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False
