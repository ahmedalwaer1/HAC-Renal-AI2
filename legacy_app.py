"""HAC-Renal AI - Streamlit UI (chat + clinical follow-up).

Two tabs share one deterministic core:

  * "المحادثة" - the clinician writes a note in any language; the model extracts
    structured data and narrates the answer, while every number still comes from
    rules_engine.py.
  * "متابعة الحالة" - a case is opened, follow-up events are recorded and the
    same engine is re-run to report what changed (stage 4).

The prose is produced by the model, the decision card is produced by Python, so a
misbehaving model can never change a regimen.
"""
import json
import os
import urllib.request

import streamlit as st
from dotenv import load_dotenv, set_key

import followup_engine as fu
from rules_engine import apply_rules
from evidence_retriever import retrieve_evidence
from agents.llm_agent import compose_clinical_reply, extract_patient_from_text
from data.clinical_data import get_source
from data.drug_registry import supported_drugs
from data.followup_rules import (
    ADVERSE_EFFECT_OPTIONS,
    CLINICAL_RESPONSE_OPTIONS,
    FOLLOWUP_EVENT_TYPES,
)

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(ENV_PATH)

MISTRAL_MODELS = ["mistral-large-latest", "open-mistral-nemo"]
FREE_ROUTER = "openrouter/free"
CUSTOM_MODEL = "مخصص (اكتب المعرّف)"
AUTO_DRUG = "تلقائي (من الرسالة)"
FALLBACK_FREE_MODELS = [
    "deepseek/deepseek-chat-v3-0324:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "google/gemini-2.0-flash-exp:free",
]
EVENT_LABELS = {t["code"]: t["label"] for t in FOLLOWUP_EVENT_TYPES}

# Severity codes as they read to a pharmacist (never the raw STOP/ADJUST form).
SEVERITY_LABELS = {
    "STOP": "إيقاف مؤقت ومراجعة",
    "ESCALATE": "تصعيد لمراجعة أخصائي",
    "ADJUST": "تعديل النظام الجرعي",
    "REVIEW": "مراجعة سريرية",
}

# Engine decision codes as they read to a pharmacist (never the raw code).
DECISION_LABELS = {
    "BLOCK": "توقف التسجيل الآلي",
    "HIGH_PRIORITY_INTERACTION_ALERT": "تنبيه تداخل دوائي عالي الأهمية",
    "SPECIALIST_REVIEW_REQUIRED": "مطلوب مراجعة أخصائي",
    "SOURCE_DATA_UNAVAILABLE": "بيانات المصدر غير متاحة",
    "USE_SHORT_INFUSION": "استخدام تسريب قصير المدة",
    "OUT_OF_DECLARED_BOUNDS": "خارج النطاق المعتمد",
    "RENAL_ADJUSTED_REGIMEN_SELECTED": "تم اختيار جرعة معدّلة لكلوي",
    "DIALYSIS_SPECIFIC_REGIMEN_SELECTED": "تم اختيار جرعة خاصة بالغسيل الكلوي",
    "EXTENDED_INFUSION_REGIMEN_SELECTED": "تم اختيار نظام تسريب ممتد",
}

# Internal patient keys named exactly as a pharmacist needs to supply them.
MISSING_FIELD_LABELS = {
    "requested_drug": "الدواء المطلوب (ميروبينيم أو فانكومايسين)",
    "dialysis_status": "حالة الغسيل الكلوي (على غسيل / ليس على غسيل)",
    "dialysis_modality": "طريقة الغسيل الكلوي (IHD / CRRT / CVVHD / PD)",
    "crcl": "معدل الترشيح الكلوي CrCl بوحدة mL/min، أو الكرياتينين (mg/dL) "
            "مع الجنس والوزن والعمر لحسابه",
    "indication_group": "التشخيص السريري للعدوى (مثال: التهاب رئوي، التهاب سحايا)",
    "infection_type": "نوع العدوى (مثال: تجرثم دم MRSA، التهاب رئوي)",
    "infusion_strategy": "استراتيجية التسريب (تسريب قصير المدة / تسريب ممتد)",
    "age_years": "العمر بالسنوات",
    "weight_kg": "الوزن بالكيلوجرام",
}

st.set_page_config(page_title="HAC-Renal AI", layout="wide")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_free_tool_models():
    """اجلب موديلات OpenRouter المجانية التي تدعم استدعاء الأدوات، مرتّبة من الأفضل."""
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"User-Agent": "hac-renal-ai"},
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []

    candidates = []
    for m in payload.get("data", []):
        pricing = m.get("pricing") or {}
        try:
            is_free = (
                float(pricing.get("prompt") or 1) == 0
                and float(pricing.get("completion") or 1) == 0
            )
        except (TypeError, ValueError):
            is_free = False
        if is_free and "tools" in (m.get("supported_parameters") or []):
            candidates.append(
                {"id": m.get("id", ""), "context_length": m.get("context_length") or 0}
            )

    def sort_key(model):
        # الموديلات التجريبية/المؤقتة آخر القائمة، والباقي بحسب طول السياق
        unstable = 1 if (
            "stealth/" in model["id"] or "preview" in model["id"]
        ) else 0
        return (unstable, -model["context_length"])

    return [m["id"] for m in sorted(candidates, key=sort_key)]


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
st.sidebar.title("HAC-Renal AI")

if "api_key" not in st.session_state:
    saved_key = os.getenv("LLM_API_KEY", "")
    st.session_state["api_key"] = "" if saved_key == "your_api_key_here" else saved_key

api_key = st.sidebar.text_input(
    "API Key",
    type="password",
    key="api_key",
    help="OpenRouter أو Mistral key. اتركه فارغاً لتستخدم المحرك الحتمي بدون محادثة.",
)

provider = st.sidebar.selectbox("Provider", ["OpenRouter", "Mistral"], index=0)
if provider == "OpenRouter":
    base_url = "https://openrouter.ai/api/v1"
    free_models = fetch_free_tool_models()
    others = [m for m in (free_models[:15] or FALLBACK_FREE_MODELS) if m != FREE_ROUTER]
    model_list = [FREE_ROUTER] + others
else:
    base_url = "https://api.mistral.ai/v1"
    free_models = []
    model_list = MISTRAL_MODELS

model_choice = st.sidebar.selectbox(
    "Model",
    model_list + [CUSTOM_MODEL],
    index=0,
    help="openrouter/free = راوتر OpenRouter يختار أفضل موديل مجاني تلقائياً لكل طلب.",
)
if model_choice == CUSTOM_MODEL:
    model_name = st.sidebar.text_input("Model ID", value="")
else:
    model_name = model_choice

if st.sidebar.button("حفظ المفتاح"):
    set_key(ENV_PATH, "LLM_API_KEY", api_key)
    set_key(ENV_PATH, "LLM_BASE_URL", base_url)
    set_key(ENV_PATH, "LLM_MODEL_NAME", model_name)
    st.sidebar.success("تم الحفظ في .env")

has_key = bool(api_key) and api_key != "your_api_key_here"

st.sidebar.caption(
    f"Model: `{model_name or '—'}`  \n"
    f"Key: {'محفوظ ✓' if os.getenv('LLM_API_KEY') not in (None, '', 'your_api_key_here') else 'غير محفوظ'}"
)
if provider == "OpenRouter":
    if model_choice == FREE_ROUTER:
        st.sidebar.caption("راوتر مجاني تلقائي: OpenRouter يختار الموديل المجاني الأنسب بنفسه.")
    elif free_models:
        st.sidebar.caption(f"{len(free_models)} موديل مجاني يدعم استدعاء الأدوات.")
    else:
        st.sidebar.warning("تعذّر جلب قائمة OpenRouter، تم استخدام قائمة افتراضية.")

default_drug = st.sidebar.selectbox(
    "العقار الافتراضي",
    [AUTO_DRUG] + supported_drugs(),
    index=0,
    help="يُستخدم فقط إذا لم تُسمِّ العقار في رسالتك.",
)
st.sidebar.caption("الأدوية المدعومة: " + "، ".join(supported_drugs()))

if st.sidebar.button("محادثة جديدة"):
    st.session_state.messages = []
    st.session_state.known_patient = {}
    st.rerun()

# ---------------------------------------------------------------------------
# Shared rendering helpers
# ---------------------------------------------------------------------------
def _clinical_reference(result, evidence=None):
    """Name the reference a pharmacist would cite (issuing body + document).

    Internal rule ids such as MER-001 are never shown; they are replaced by the
    responsible body and document behind the decision.
    """
    for src in (evidence or {}).get("sources") or []:
        if src.get("title"):
            return " — ".join(
                part for part in (src.get("organization"), src.get("title")) if part
            )
    descriptive = (result or {}).get("source_rule") or ""
    # A short token such as MER-001 carries no space and is not shown to clinicians.
    return descriptive if " " in descriptive else "محرك القواعد السريرية المعتمد"


def render_result(result, evidence=None):
    """Render the deterministic decision (the ground truth, never the model)."""
    decision = result.get("decision", "")
    message = result.get("message") or ""

    if decision == "BLOCK":
        st.error("متوقف: " + message)
    elif decision == "HIGH_PRIORITY_INTERACTION_ALERT":
        st.warning("تنبيه تداخل دوائي عالي الأهمية: " + message)
    elif decision in ("SPECIALIST_REVIEW_REQUIRED", "SOURCE_DATA_UNAVAILABLE",
                      "USE_SHORT_INFUSION", "OUT_OF_DECLARED_BOUNDS"):
        st.warning("%s: %s" % (DECISION_LABELS.get(decision, "تنبيه سريري"), message))
    elif decision == "NEEDS_MORE_INFORMATION":
        st.info("المعلومات المتاحة غير كافية لاختيار جرعة آمنة، ولم يتم توليد أي جرعة.")
    elif decision == "UNSUPPORTED_DRUG":
        st.info(message or "الدواء المطلوب غير مدعوم في القواعد المعتمدة؛ لم يتم توليد جرعة.")
    else:
        st.success(DECISION_LABELS.get(decision) or "تم اختيار النظام الجرعي")

    if result.get("required_action") and not result.get("missing_fields"):
        st.caption("الإجراء المطلوب: " + str(result["required_action"]))
    missing_labels = [
        MISSING_FIELD_LABELS.get(f, f) for f in result.get("missing_fields") or []
    ]
    if missing_labels:
        st.markdown("**المعلومات الناقصة لإكمال التقييم الطبي بالضبط:**")
        for label in missing_labels:
            st.markdown("- %s" % label)
        st.caption("ابعت القيم دي في رسالة جديدة وهنحسبلك الجرعة فورًا.")

    dose = result.get("dose")
    if dose is not None:
        st.metric("الجرعة", "%s %s" % (dose, result.get("dose_unit", "")))
    elif result.get("dose_mg_per_kg"):
        st.metric("الجرعة", "%s mg/kg" % result["dose_mg_per_kg"])

    facts = [
        ("المرجع السريري", _clinical_reference(result, evidence)),
        ("الطريق", result.get("route")),
        ("التكرار", result.get("frequency")),
    ]
    cols = st.columns(3)
    for col, (label, value) in zip(cols, facts):
        col.markdown("**%s**  \n%s" % (label, value or "—"))

    findings = result.get("therapy_assessment") or []
    if findings:
        with st.expander("ملاءمة العلاج (%d)" % len(findings)):
            for f in findings:
                st.markdown("- **%s — %s**: %s"
                            % (f.get("severity", ""), f.get("category", ""),
                               f.get("rule", "")))

    plan = result.get("monitoring_plan") or {}
    if plan:
        with st.expander("خطة المتابعة وإعادة التقييم"):
            for item in (plan.get("common", []) + plan.get("dialysis_specific", [])
                         + plan.get("drug_specific", [])):
                st.markdown("- **%s** — %s" % (item.get("parameter", ""),
                                               item.get("detail", "")))
            for trigger in plan.get("reassessment_triggers", []):
                st.markdown("- عند *%s* ← %s" % (trigger.get("trigger", ""),
                                                 trigger.get("action", "")))

    sources = (evidence or {}).get("sources") or []
    sections = (evidence or {}).get("sections") or []
    if sources or sections:
        with st.expander("المراجع والاستشهادات"):
            for src in sources:
                if src.get("url"):
                    label = " — ".join(
                        part for part in (src.get("organization"), src.get("title"))
                        if part
                    ) or src.get("key")
                    st.markdown("- [%s](%s)" % (label, src["url"]))
            for section in sections:
                heading = section.get("section") or section.get("citation") or ""
                if heading:
                    st.markdown("**%s**" % heading)
                quoted = "\n".join(
                    "> " + line for line in section["snippet"][:400].splitlines()
                )
                st.markdown(quoted)


def render_reassessment(assessment):
    """Render one follow-up re-assessment produced by followup_engine.py."""
    severity = assessment.get("severity")
    headline = "%s — %s" % (SEVERITY_LABELS.get(severity, severity or ""),
                            assessment.get("action"))
    if severity in ("STOP", "ESCALATE"):
        st.error(headline)
    elif severity in ("ADJUST", "REVIEW"):
        st.warning(headline)
    else:
        st.success(headline)

    level = assessment.get("level_assessment")
    if level:
        if level.get("status") in ("BELOW_TARGET", "ABOVE_TARGET", "WITHIN_TARGET"):
            st.markdown(
                "**TDM:** %s = %s %s | الهدف %s → **%s**"
                % (level.get("metric"), level.get("value"), level.get("unit", ""),
                   level.get("target_label"), level.get("direction"))
            )
        else:
            st.markdown("**TDM:** %s" % (level.get("message") or level.get("status")))
        if level.get("note"):
            st.caption(level["note"])

    change = assessment.get("regimen_change") or {}
    if change.get("changed"):
        st.markdown("**تغيّر النظام الجرعي:**")
        for diff in change["fields"]:
            st.markdown("- `%s`: %s → %s" % (diff["field"], diff["before"],
                                             diff["after"]))
    else:
        st.caption("لا تغيّر في النظام الجرعي.")

    if assessment.get("crcl_recomputed_from_creatinine"):
        st.caption("تم تجاهل CrCl المخزّن وإعادة حسابه من الكرياتينين الجديد.")
    if assessment.get("empirical_flag_cleared"):
        st.caption("تم رفع علامة «علاج تجريبي» بعد توفر المزرعة.")
    if assessment.get("hold_automated_recommendation"):
        st.caption("تم إيقاف التوصية الآلية لحين مراجعة الصيدلي.")
    if assessment.get("requires_pharmacist_action"):
        st.caption("مطلوب إجراء من الصيدلي.")

    source = get_source(assessment.get("source"))
    if source:
        st.caption("المصدر: %s" % source.get("title"))


def run_engine(patient):
    """Run the deterministic engine plus retrieval, returning (result, evidence)."""
    result = apply_rules(patient)
    return result, retrieve_evidence(result)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
st.title("HAC-Renal AI — مساعد قرار الجرعات الكلوية")
st.caption(
    "استخراج بالذكاء الاصطناعي، وحساب الجرعة بمحرك حتمي بلغة بايثون، ومتابعة سريرية "
    "بنفس المحرك. أداة دعم قرار فقط — تحقّق من البروتوكول المحلي قبل الوصف."
)

tab_chat, tab_followup = st.tabs(["المحادثة", "متابعة الحالة"])

# ===========================================================================
# Tab 1 - chat
# ===========================================================================
with tab_chat:
    st.caption(
        "اكتب بيانات المريض بأي لغة داخل شريط المحادثة، ويمكنك استخدام الإدخال اليدوي "
        "السريع الذي يعمل بدون مفتاح."
    )

    with st.expander("إدخال يدوي سريع (يعمل بدون مفتاح)"):
        with st.form("patient_form"):
            c1, c2 = st.columns(2)
            with c1:
                drug = st.selectbox("Drug", supported_drugs(), index=0)
                age = st.number_input("Age (years)", 18, 120, 60)
                weight = st.number_input("Weight (kg)", 30, 200, 70)
                gender = st.selectbox("Gender", ["Male", "Female"], index=0)
                creatinine = st.number_input("Serum Creatinine (mg/dL)", 0.1, 20.0, 1.0,
                                             step=0.1)
            with c2:
                dialysis_status = st.selectbox("Dialysis", ["No", "IHD", "CRRT", "PD"],
                                               index=0)
                if drug == "Meropenem":
                    indication = st.selectbox("Indication",
                                              ["Standard", "Meningitis_CF"], index=0)
                    infusion = st.selectbox(
                        "Infusion Strategy",
                        ["Short_Infusion", "Extended_Infusion"], index=0
                    )
                else:
                    infection_type = st.selectbox(
                        "Infection Type", ["complicated", "uncomplicated"], index=0
                    )
                cvvhd_flow = st.number_input(
                    "CVVHD flow rate (L/hour, CRRT only)", 0.0, 10.0, 0.0, step=0.5
                )
                allergy_text = st.text_input("Allergy (substance)", "")
                med_text = st.text_input("Concomitant medications (comma separated)", "")
            submitted = st.form_submit_button("احسب الجرعة")

    if submitted:
        allergy_history = (
            [{"substance": allergy_text.strip(), "reaction": "",
              "certainty": "confirmed"}] if allergy_text.strip() else []
        )
        concomitant = [{"drug": m.strip()} for m in med_text.split(",") if m.strip()]
        if dialysis_status == "No":
            dialysis = {"status": "No"}
        else:
            dialysis = {"status": "Yes", "modality": dialysis_status}
            if dialysis_status == "CRRT" and cvvhd_flow > 0:
                dialysis["flow_rate_l_per_hour"] = cvvhd_flow

        manual_patient = {
            "requested_drug": drug,
            "age_years": age,
            "weight_kg": weight,
            "gender": gender,
            "creatinine": creatinine,
            "allergy_history": allergy_history,
            "concomitant_medications": concomitant,
            "dialysis": dialysis,
        }
        if drug == "Meropenem":
            manual_patient["indication_group"] = indication
            manual_patient["infusion_strategy"] = infusion
        else:
            manual_patient["infection_type"] = infection_type

        st.session_state.known_patient = manual_patient
        result, evidence = run_engine(manual_patient)
        st.session_state.messages.append(
            {"role": "assistant", "text": "", "result": result, "evidence": evidence}
        )
        st.rerun()

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "known_patient" not in st.session_state:
        st.session_state.known_patient = {}

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message.get("text"):
                st.markdown(message["text"])
            if message.get("result"):
                render_result(message["result"], message.get("evidence"))

    prompt = st.chat_input(
        "اكتب بيانات المريض بأي لغة… مثال: مريضة 68 سنة، 65 كجم، كرياتينين 1.4، "
        "محتاجة فانكومايسين لالتهاب رئوي"
    )

    if prompt:
        st.session_state.messages.append({"role": "user", "text": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if not has_key:
                st.info(
                    "المحادثة تحتاج API Key في الشريط الجانبي. يمكنك حالياً استخدام "
                    "«إدخال يدوي سريع» بالأعلى للحصول على الجرعة الحتمية."
                )
            else:
                try:
                    with st.spinner("جاري استخراج البيانات..."):
                        extracted, language = extract_patient_from_text(
                            prompt, api_key, base_url, model_name,
                            known=st.session_state.known_patient,
                        )
                except Exception as exc:
                    extracted, language = {}, None
                    st.caption("تعذّر استخراج بيانات منظّمة: %s" % exc)

                patient = fu.merge_patient_input(st.session_state.known_patient,
                                                 extracted)
                if default_drug != AUTO_DRUG and not patient.get("requested_drug"):
                    patient["requested_drug"] = default_drug
                st.session_state.known_patient = patient

                result, evidence = run_engine(patient)

                narration = ""
                try:
                    with st.spinner("جاري صياغة الرد..."):
                        narration = compose_clinical_reply(
                            prompt, result, evidence, language,
                            api_key, base_url, model_name,
                        )
                except Exception as exc:
                    st.caption("تعذّر توليد السرد: %s" % exc)

                if narration:
                    st.markdown(narration)
                render_result(result, evidence)

                with st.expander("البيانات المستخرجة (للمراجعة)"):
                    st.json(patient)

                st.session_state.messages.append(
                    {"role": "assistant", "text": narration, "result": result,
                     "evidence": evidence}
                )

# ===========================================================================
# Tab 2 - clinical follow-up
# ===========================================================================
with tab_followup:
    st.caption(
        "افتح حالة، ثم سجّل أحداث المتابعة (كرياتينين جديد، مستوى دواء، جلسة دياليزة، "
        "مزرعة، استجابة سريرية، أثر جانبي). يعيد المحرك الحتمي حساب النظام الجرعي "
        "ويخبرك بما تغيّر."
    )

    if "active_case" not in st.session_state:
        st.session_state["active_case"] = None
    if "last_reassessment" not in st.session_state:
        st.session_state["last_reassessment"] = None

    saved = fu.list_cases()
    case_labels = {"": "— اختر حالة محفوظة —"}
    for summary in saved:
        case_labels[summary["case_id"]] = "%s | %s | %s | %s" % (
            summary["case_id"], summary["label"] or "بدون وصف",
            summary["drug"] or "-", summary["decision"] or "-",
        )

    col_saved, col_open = st.columns([3, 2])
    with col_saved:
        picked = st.selectbox("الحالات المحفوظة", list(case_labels.keys()),
                              format_func=lambda key: case_labels[key])
        if st.button("افتح الحالة المحفوظة") and picked:
            st.session_state["active_case"] = fu.load_case(picked)
            st.session_state["last_reassessment"] = None
            st.rerun()
    with col_open:
        case_label = st.text_input("وصف الحالة (اختياري)", "")
        if st.button("افتح حالة جديدة من آخر بيانات المحادثة"):
            patient = st.session_state.get("known_patient") or {}
            if not patient:
                st.warning("لا توجد بيانات بعد. اكتب بيانات المريض في تاب المحادثة أولاً.")
            else:
                case = fu.open_case(patient, label=case_label)
                fu.save_case(case)
                st.session_state["active_case"] = case
                st.session_state["last_reassessment"] = None
                st.rerun()

    case = st.session_state.get("active_case")

    if not case:
        st.info("افتح حالة جديدة أو اختر حالة محفوظة للبدء في المتابعة.")
    else:
        st.markdown("### الحالة `%s`" % case["case_id"])
        st.caption(
            "آخر تحديث: %s | الدواء: %s | عدد أحداث المتابعة: %d"
            % (case.get("updated_at"), case.get("drug"),
               max(len(case.get("timeline") or []) - 1, 0))
        )

        if st.session_state.get("last_reassessment"):
            st.markdown("#### نتيجة آخر إعادة تقييم")
            render_reassessment(st.session_state["last_reassessment"])

        with st.expander("النظام الجرعي الحالي", expanded=True):
            render_result(case["current_result"])

        st.markdown("#### الاستحقاقات القادمة")
        for item in case.get("next_due", []):
            source = get_source(item.get("source"))
            st.markdown("- **%s** — %s  \n<span style='color:gray;font-size:0.8em'>%s</span>"
                        % (item["item"], item["due"],
                           (source or {}).get("title", "")),
                        unsafe_allow_html=True)

        st.markdown("#### الخط الزمني")
        timeline = case.get("timeline") or []
        for entry in reversed(timeline):
            title = "%s — %s" % (entry["at"], EVENT_LABELS.get(entry["event"],
                                                               entry["event"]))
            with st.expander(title, expanded=False):
                if entry.get("note"):
                    st.caption(entry["note"])
                regimen = entry.get("regimen") or {}
                st.markdown(
                    "**النظام:** %s %s %s"
                    % (regimen.get("dose", "—"), regimen.get("dose_unit", ""),
                       regimen.get("frequency", "—"))
                )
                if entry.get("reassessment"):
                    render_reassessment(entry["reassessment"])
                with st.expander("بطاقة القرار الكاملة"):
                    render_result(entry.get("result") or {})

        st.markdown("#### تسجيل حدث متابعة")
        event_code = st.selectbox(
            "نوع الحدث",
            [t["code"] for t in FOLLOWUP_EVENT_TYPES],
            format_func=lambda code: EVENT_LABELS.get(code, code),
        )

        with st.form("followup_event_form"):
            data = {}
            if event_code == "renal_function":
                c1, c2 = st.columns(2)
                data["creatinine"] = c1.number_input(
                    "Serum creatinine (mg/dL)", 0.1, 20.0,
                    float(case["patient"].get("creatinine") or 1.0), step=0.1)
                crcl_input = c2.number_input("CrCl (mL/min، اختياري)", 0.0, 200.0,
                                             0.0, step=1.0)
                data["crcl_ml_min"] = crcl_input or None
            elif event_code == "drug_level":
                c1, c2 = st.columns(2)
                data["level_type"] = c1.selectbox("نوع المستوى", ["auc", "trough"])
                data["value"] = c2.number_input("القيمة", 0.0, 2000.0, 0.0, step=1.0)
            elif event_code == "dialysis_session":
                c1, c2 = st.columns(2)
                data["modality"] = c1.selectbox("الطريقة", ["IHD", "CRRT", "CVVHD", "PD"])
                flow = c2.number_input("CVVHD flow (L/hour، اختياري)", 0.0, 10.0, 0.0,
                                       step=0.5)
                if flow:
                    data["flow_rate_l_per_hour"] = flow
            elif event_code == "microbiology":
                data["culture_result"] = st.text_input(
                    "Culture / susceptibility", "MRSA, vancomycin S")
            elif event_code == "clinical_response":
                data["response"] = st.selectbox("الاستجابة", CLINICAL_RESPONSE_OPTIONS)
            elif event_code == "adverse_effect":
                data["effect"] = st.selectbox("الأثر الجانبي", ADVERSE_EFFECT_OPTIONS)
                new_cr = st.number_input("Creatinine جديد (اختياري)", 0.0, 20.0, 0.0,
                                         step=0.1)
                if new_cr:
                    data["creatinine"] = new_cr
            elif event_code == "medication_change":
                text = st.text_input("الأدوية الجديدة (مفصولة بفاصلة)", "")
                data["medications"] = [m.strip() for m in text.split(",") if m.strip()]
            elif event_code == "duration_review":
                data["day"] = st.number_input("يوم العلاج", 1, 42, 3)

            note = st.text_input("ملاحظة (اختياري)", "")
            record = st.form_submit_button("سجّل الحدث وأعد التقييم")

        if record:
            if event_code == "drug_level" and not data.get("value"):
                st.warning("أدخل قيمة المستوى.")
            else:
                reassessment = fu.record_event(
                    case, {"type": event_code, "data": data, "note": note})
                fu.save_case(case)
                st.session_state["last_reassessment"] = reassessment
                st.rerun()

        st.divider()
        if st.button("حذف هذه الحالة"):
            fu.delete_case(case["case_id"])
            st.session_state["active_case"] = None
            st.session_state["last_reassessment"] = None
            st.rerun()
