"""HAC Renal AI — premium clinical workspace; existing deterministic engine retained."""
import os, json, html
from datetime import datetime
from pathlib import Path
import streamlit as st
from dotenv import load_dotenv
from rules_engine import apply_rules
from evidence_retriever import retrieve_evidence
import followup_engine as fu
from data.drug_registry import supported_drugs
from data.followup_rules import FOLLOWUP_EVENT_TYPES
from agents.llm_agent import extract_patient_from_text, compose_clinical_reply

ROOT=Path(__file__).parent
load_dotenv(ROOT/'.env')
st.set_page_config(page_title='HAC • Renal Intelligence',page_icon='🩺',layout='wide',initial_sidebar_state='expanded')

CSS='''
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Outfit:wght@400;500;600;700;800&display=swap');
:root{--navy:#071d2c;--teal:#00b8a0;--muted:#718498;--border:#e8eef3}
html,body,[class*="css"],.stApp{font-family:'DM Sans',sans-serif}
.stApp{background:#f5f8fb;color:#142b3c}
[data-testid="stSidebar"]{background:#071d2c!important;border-right:1px solid #12384a}
[data-testid="stSidebar"] *{color:#d8e9f1}
[data-testid="stSidebar"] label{color:#b8cedb!important}
[data-testid="stSidebar"] [data-baseweb="select"] *{color:#132b39!important}
[data-testid="stSidebar"] input{color:#172e3a!important}
.block-container{padding:2rem 3rem 4rem;max-width:1550px}
h1,h2,h3{font-family:'Outfit',sans-serif;letter-spacing:-.035em;color:#0b293a}
h1{font-size:2.35rem!important;font-weight:800!important}
h3{font-weight:750!important}
.hero{display:flex;align-items:center;justify-content:space-between;gap:24px;background:linear-gradient(115deg,#082b3a 0%,#0a4050 60%,#086f71 100%);border-radius:24px;padding:32px 38px;box-shadow:0 16px 40px #062a3b20;min-height:215px;overflow:hidden;position:relative}
.hero:before{content:'';position:absolute;width:420px;height:420px;border:1px solid #ffffff16;border-radius:50%;right:-80px;top:-120px;box-shadow:0 0 0 50px #ffffff07,0 0 0 100px #ffffff05}
.hero h1{color:white!important;font-size:2.45rem!important;margin:8px 0 10px!important}
.hero p{color:#b9d9e1;font-size:1rem;max-width:560px;line-height:1.65;margin:0}
.eyebrow{color:#5be3ce!important;letter-spacing:.18em;font-size:.72rem;font-weight:800}
.kidney{width:200px;min-width:170px;position:relative;z-index:1;filter:drop-shadow(0 10px 22px #001a2e50)}
.metric{background:#fff;border:1px solid #e7eef3;border-radius:19px;padding:20px 22px;box-shadow:0 5px 20px #103b4d07;min-height:125px}
.metric .label{font-size:.8rem;color:#7b8e9e;font-weight:700}.metric .number{font-family:Outfit;font-size:2rem;font-weight:800;color:#102f41;margin-top:10px}.metric .hint{font-size:.75rem;color:#0b9b8e;margin-top:4px}
.section-title{font-family:Outfit;font-size:1.25rem;font-weight:800;color:#102e40;margin:24px 0 14px}
.panel{background:#fff;border:1px solid #e7eef3;border-radius:18px;padding:20px 23px;margin:8px 0 18px}
.pill{display:inline-block;background:#d9f8f0;color:#087e70;border-radius:50px;padding:5px 11px;font-size:.72rem;font-weight:800;letter-spacing:.06em}
.pill.warn{background:#fff0d7;color:#b86c12}.pill.danger{background:#ffe3e3;color:#b52f3d}
.status{border-left:4px solid #00b8a0;background:#ecfaf7;border-radius:12px;padding:15px 18px;color:#13574f;margin:12px 0}
.status.warn{border-color:#e6a238;background:#fff8e8;color:#7a551b}.status.danger{border-color:#db5962;background:#fff0f1;color:#9e2734}
.small{font-size:.83rem;color:#7c91a0;line-height:1.6}
.stButton>button[kind="primary"]{background:#008e84!important;border:0!important;color:white!important;border-radius:12px!important;font-weight:700!important}
.stButton>button{border-radius:12px!important;font-weight:700!important;min-height:40px}
[data-testid="stForm"]{background:#fff;border:1px solid #e7eef3;border-radius:19px;padding:22px}
[data-testid="stTabs"] [role="tab"]{font-weight:750;padding:13px 18px}
[data-testid="stTabs"] [aria-selected="true"]{color:#008e84!important}
[data-testid="stChatMessage"]{background:white;border:1px solid #e7eef3;border-radius:15px}
hr{border-color:#e9eef2}
@media(max-width:800px){.block-container{padding:1.2rem}.hero{padding:24px}.hero h1{font-size:1.75rem!important}.kidney{width:110px;min-width:100px}}
</style>
'''
st.markdown(CSS,unsafe_allow_html=True)
KIDNEY='''<svg class="kidney" viewBox="0 0 220 210" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="g" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#73e9db"/><stop offset="1" stop-color="#12a89e"/></linearGradient></defs><path d="M76 34C32 20 10 59 21 109c9 43 49 61 72 35 13-15 11-32-3-43-18-14-11-29-2-39 10-11 2-23-12-28Z" fill="url(#g)" opacity=".95"/><path d="M144 34c44-14 66 25 55 75-9 43-49 61-72 35-13-15-11-32 3-43 18-14 11-29 2-39-10-11-2-23 12-28Z" fill="url(#g)" opacity=".95"/><path d="M99 94c10-12 14-12 22 0M110 85v85" stroke="#f7c7a8" stroke-width="8" stroke-linecap="round" fill="none"/><path d="M57 49c-19 5-27 23-23 42M163 49c19 5 27 23 23 42" stroke="#c2fff1" stroke-width="5" stroke-linecap="round" fill="none" opacity=".65"/><circle cx="110" cy="178" r="8" fill="#c9f6e8"/></svg>'''

if 'messages' not in st.session_state:st.session_state.messages=[]
if 'patient' not in st.session_state:st.session_state.patient={}
if 'latest' not in st.session_state:st.session_state.latest=None
if 'active_case' not in st.session_state:st.session_state.active_case=None

with st.sidebar:
 st.markdown('<div style="font-family:Outfit;font-size:1.65rem;font-weight:800;color:white;padding:15px 0 2px">✦ HAC<span style="color:#52e3cd"> / RENAL</span></div><div style="font-size:.7rem;letter-spacing:.2em;color:#83a7b7;margin-bottom:22px">CLINICAL INTELLIGENCE</div>',unsafe_allow_html=True)
 st.markdown('---')
 st.markdown('**WORKSPACE**')
 st.caption('Clinical decision-support prototype')
 st.markdown('---')
 st.markdown('**AI CONNECTION**')
 provider=st.selectbox('Provider',['OpenRouter','Mistral'],label_visibility='collapsed')
 base_url='https://openrouter.ai/api/v1' if provider=='OpenRouter' else 'https://api.mistral.ai/v1'
 model=st.text_input('Model ID',value=os.getenv('LLM_MODEL_NAME','openrouter/free') if provider=='OpenRouter' else 'mistral-large-latest')
 api_key=st.text_input('API key (session only)',value=os.getenv('LLM_API_KEY',''),type='password')
 st.caption('Keys are kept in session; never included in exports.')
 st.markdown('---')
 st.markdown('<div class="pill">● RULE ENGINE READY</div>',unsafe_allow_html=True)
 st.caption('Vancomycin · Meropenem')
 st.markdown('---')
 st.caption('⚕ Research prototype · Clinician review required')

st.markdown(f'''<div class="hero"><div><div class="eyebrow">NEXT-GENERATION RENAL CARE</div><h1>Clinical intelligence,<br/>beautifully connected.</h1><p>Evidence-grounded antibiotic review, patient case monitoring, and AI-assisted clinical reasoning — in one refined workspace.</p><div style="margin-top:18px"><span class="pill">● CLINICAL WORKSPACE</span></div></div>{KIDNEY}</div>''',unsafe_allow_html=True)

cases=fu.list_cases()
alerts=sum(1 for c in cases if c.get('decision') in ('BLOCK','SPECIALIST_REVIEW_REQUIRED','HIGH_PRIORITY_INTERACTION_ALERT'))
a,b,c,d=st.columns(4)
for col,label,num,hint in [(a,'Tracked cases',len(cases),'Local case records'),(b,'Supported antibiotics','02','Clinical rules connected'),(c,'Review flags',alerts,'From saved decisions'),(d,'Clinical engine','ACTIVE','Deterministic safety layer')]:
 with col:st.markdown(f'<div class="metric"><div class="label">{label}</div><div class="number">{num}</div><div class="hint">{hint}</div></div>',unsafe_allow_html=True)

st.markdown('<div class="section-title">Clinical workspace</div>',unsafe_allow_html=True)
tab_over,tab_review,tab_ai,tab_cases,tab_about=st.tabs(['◈ Overview','✚ Medication review','✦ AI copilot','▤ Case timeline','ⓘ About & safety'])

def evaluate(p):
 result=apply_rules(p)
 try:evidence=retrieve_evidence(result)
 except Exception:evidence={}
 st.session_state.patient=p
 st.session_state.latest=(result,evidence)
 return result,evidence

def show_result(result,evidence=None):
 decision=result.get('decision','UNKNOWN');msg=html.escape(str(result.get('message') or ''))
 dangerous=decision in ('BLOCK','HIGH_PRIORITY_INTERACTION_ALERT')
 review=decision in ('SPECIALIST_REVIEW_REQUIRED','NEEDS_MORE_INFORMATION','SOURCE_DATA_UNAVAILABLE','OUT_OF_DECLARED_BOUNDS','UNSUPPORTED_DRUG')
 kind='danger' if dangerous else 'warn' if review else ''
 title='STOP / HIGH-PRIORITY ALERT' if dangerous else 'CLINICIAN REVIEW REQUIRED' if review else 'RULE ENGINE OUTPUT'
 st.markdown(f'<div class="status {kind}"><strong>{title}</strong><br/><span style="font-size:.85rem">{html.escape(decision)}</span><br/>{msg}</div>',unsafe_allow_html=True)
 fields=result.get('missing_fields') or []
 if fields:st.warning('Missing required information: '+', '.join(str(x) for x in fields))
 regimen=result.get('regimen') or {}
 if regimen:
  st.markdown('**Engine-generated regimen (requires clinician verification)**')
  st.json(regimen)
 action=result.get('required_action')
 if action:st.info('Required action: '+str(action))
 if evidence:
  with st.expander('Evidence & traceability'):
   for src in evidence.get('sources') or []:
    st.write('•',src.get('title') or src.get('organization') or 'Reference')
   if not evidence.get('sources'):st.caption('No source references available in this result.')
 with st.expander('Raw decision record'):st.json(result)

with tab_over:
 left,right=st.columns([1.55,1])
 with left:
  st.markdown('<div class="section-title">Your clinical command center</div>',unsafe_allow_html=True)
  st.markdown('''<div class="panel"><span class="pill">01 / REVIEW</span><h3>Structured antibiotic assessment</h3><p class="small">Enter patient context and run the existing deterministic dosing and safety engine. All clinical results come from the original backend.</p></div><div class="panel"><span class="pill">02 / REASON</span><h3>AI-powered clinical copilot</h3><p class="small">Convert clinical notes into structured fields, then verify findings through the same rules engine and supporting evidence.</p></div><div class="panel"><span class="pill">03 / MONITOR</span><h3>Longitudinal case follow-up</h3><p class="small">Open saved cases, review historical events, and record new follow-up observations.</p></div>''',unsafe_allow_html=True)
 with right:
  st.markdown('<div class="section-title">Recent cases</div>',unsafe_allow_html=True)
  if cases:
   for item in cases[:6]:
    st.markdown(f'<div class="panel"><b>{html.escape(str(item.get("label") or item.get("case_id") or "Case"))}</b><div class="small">{html.escape(str(item.get("drug") or "Unknown drug"))} · {html.escape(str(item.get("decision") or "Pending"))}</div></div>',unsafe_allow_html=True)
  else:st.info('No saved cases yet. Complete a medication review to begin.')
  st.markdown('<div class="panel"><b>🔒 Clinical safety first</b><p class="small">This workspace does not prescribe autonomously. Verify every recommendation with qualified clinicians and local guidance.</p></div>',unsafe_allow_html=True)

with tab_review:
 st.markdown('### New medication assessment')
 st.caption('Structured inputs → deterministic clinical rules → evidence-backed review.')
 with st.form('assessment_form'):
  x,y=st.columns(2)
  with x:
   drug=st.selectbox('Requested antibiotic',supported_drugs())
   age=st.number_input('Age · years',min_value=1,max_value=120,value=58)
   weight=st.number_input('Weight · kg',min_value=1.0,max_value=350.0,value=75.0,step=0.5)
   gender=st.selectbox('Sex for renal calculation',['Male','Female'])
   creatinine=st.number_input('Serum creatinine · mg/dL',min_value=0.1,max_value=25.0,value=2.4,step=0.1)
  with y:
   dialysis_status=st.selectbox('Dialysis modality',['No','IHD','CRRT','PD'])
   if drug=='Meropenem':
    indication=st.selectbox('Indication',['Standard','Meningitis_CF'])
    infusion=st.selectbox('Infusion strategy',['Short_Infusion','Extended_Infusion'])
   else:infection=st.selectbox('Infection type',['complicated','uncomplicated'])
   flow=st.number_input('CRRT flow · L/hour (if applicable)',min_value=0.0,max_value=10.0,value=0.0,step=0.5)
   allergy=st.text_input('Known drug allergy (leave blank if none documented)')
   medications=st.text_input('Concomitant medications (comma-separated)')
  submitted=st.form_submit_button('Run clinical assessment →',type='primary',use_container_width=True)
 if submitted:
  dialysis={'status':'No'} if dialysis_status=='No' else {'status':'Yes','modality':dialysis_status}
  if dialysis_status=='CRRT' and flow>0:dialysis['flow_rate_l_per_hour']=flow
  p={'requested_drug':drug,'age_years':age,'weight_kg':weight,'gender':gender,'creatinine':creatinine,'dialysis':dialysis,'allergy_history':([{'substance':allergy,'reaction':'','certainty':'confirmed'}] if allergy.strip() else []),'concomitant_medications':[{'drug':x.strip()} for x in medications.split(',') if x.strip()]}
  if drug=='Meropenem':p.update(indication_group=indication,infusion_strategy=infusion)
  else:p['infection_type']=infection
  try:evaluate(p)
  except Exception as e:st.error(f'Clinical engine could not complete: {e}')
 if st.session_state.latest:
  result,evidence=st.session_state.latest
  st.markdown('### Assessment output')
  show_result(result,evidence)
  label=st.text_input('Case label for longitudinal follow-up',placeholder='e.g. HD review • visit 1')
  if st.button('＋ Save as tracked case',type='primary'):
   try:
    case=fu.open_case(st.session_state.patient,label=label)
    fu.save_case(case)
    st.session_state.active_case=case
    st.success('Case saved. Open Case timeline to follow up.')
   except Exception as e:st.error(str(e))

with tab_ai:
 st.markdown('### Clinical AI copilot')
 st.caption('AI extracts information from notes. The deterministic rules engine remains the source of clinical calculations.')
 if not api_key:st.info('Add an API key in the left sidebar to enable language-model features. Manual review works without a key.')
 for m in st.session_state.messages:
  with st.chat_message(m['role']):st.markdown(m['text'])
 prompt=st.chat_input('Describe the clinical case in Arabic or English…')
 if prompt:
  st.session_state.messages.append({'role':'user','text':prompt})
  if not api_key:
   reply='Connect an API key in the sidebar to extract clinical information. You can use Medication review without an API key.'
  else:
   try:
    with st.spinner('Extracting clinical context…'):
     extracted,language=extract_patient_from_text(prompt,api_key,base_url,model,known=st.session_state.patient)
     p=fu.merge_patient_input(st.session_state.patient,extracted)
     result,evidence=evaluate(p)
     reply=compose_clinical_reply(prompt,result,evidence,language,api_key,base_url,model) or 'Assessment completed; see result below.'
   except Exception as e:reply=f'Unable to complete AI extraction: {e}'
  st.session_state.messages.append({'role':'assistant','text':reply})
  st.rerun()
 if st.session_state.latest:
  with st.expander('Latest verified engine result',expanded=False):show_result(*st.session_state.latest)
  with st.expander('Extracted / current patient data'):st.json(st.session_state.patient)
 if st.button('Clear conversation'):
  st.session_state.messages=[];st.rerun()

with tab_cases:
 st.markdown('### Longitudinal case monitoring')
 st.caption('Saved case IDs here are case identifiers, not a full longitudinal patient identity system.')
 cases=fu.list_cases()
 if not cases:st.info('No saved cases. Create one from Medication review.')
 else:
  options={x['case_id']:f"{x['case_id']} · {x.get('label') or 'Unlabeled'} · {x.get('drug') or '—'}" for x in cases}
  chosen=st.selectbox('Choose a case',list(options),format_func=lambda x:options[x])
  if st.button('Open case'):
   try:st.session_state.active_case=fu.load_case(chosen)
   except Exception as e:st.error(str(e))
 case=st.session_state.active_case
 if case:
  st.markdown(f"#### {case.get('label') or case.get('case_id')}")
  st.caption(f"Case ID: {case.get('case_id')} · Updated: {case.get('updated_at','—')}")
  with st.expander('Current clinical decision',expanded=True):show_result(case.get('current_result') or {})
  st.markdown('#### Follow-up events')
  for event in reversed(case.get('timeline') or []):
   with st.expander(f"{event.get('at','')} · {event.get('event','event')}"):
    st.write(event.get('note') or 'No note')
    if event.get('reassessment'):st.json(event['reassessment'])
  st.caption('For full event entry, open the preserved original interface.')
  if st.button('Refresh selected case'):
   st.session_state.active_case=fu.load_case(case['case_id']);st.rerun()

with tab_about:
 st.markdown('### Designed for clarity. Engineered for safety.')
 st.markdown('''<div class="panel"><h3>What is real in this build?</h3><p>Medication review runs your existing <b>rules_engine.py</b>; evidence comes from <b>evidence_retriever.py</b>; follow-up cases use <b>followup_engine.py</b>; the AI copilot uses your existing LLM integration.</p><p class="small">This redesign is a frontend enhancement, not a newly validated medical device. No patient identity database, prescription-image scanner, or clinical authentication has been added. Those would require separate backend work.</p></div>''',unsafe_allow_html=True)
 st.warning('Research/demo use only. Not for autonomous diagnosis, prescribing, or use with identifiable patient information without appropriate governance and safeguards.')
 st.markdown('**Original full-feature interface:** run `streamlit run legacy_app.py` to access all original follow-up event entry and settings.')
