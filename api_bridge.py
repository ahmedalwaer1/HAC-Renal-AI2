"""Additive HTTP adapter. Existing clinical engines are imported unchanged."""
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from rules_engine import apply_rules
from evidence_retriever import retrieve_evidence
from data.drug_registry import supported_drugs
from agents.llm_agent import extract_patient_from_text, compose_clinical_reply
import followup_engine as fu

load_dotenv(Path(__file__).parent / '.env')
app = FastAPI(title='HAC Renal AI UI Adapter', version='1.0')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173','http://127.0.0.1:5173'], allow_methods=['GET','POST'], allow_headers=['Content-Type'])
class Assessment(BaseModel):
    patient: dict
class SaveCase(BaseModel):
    patient: dict
    label: str = Field(default='', max_length=120)
class ChatRequest(BaseModel):
    message: str
    known: dict = Field(default_factory=dict)
    api_key: str = ''
    model: str = 'openrouter/free'
    provider: str = 'OpenRouter'

@app.get('/api/health')
def health(): return {'status':'online','supported_drugs':supported_drugs()}
@app.get('/api/cases')
def cases(): return fu.list_cases()
@app.get('/api/cases/{case_id}')
def case(case_id: str):
    if not case_id.startswith('CASE-') or any(x in case_id for x in ('/','\\','..')): raise HTTPException(400,'Invalid case ID')
    result=fu.load_case(case_id)
    if not result: raise HTTPException(404,'Case not found')
    return result
@app.post('/api/assess')
def assess(body: Assessment):
    try:
        result=apply_rules(body.patient)
        try: evidence=retrieve_evidence(result)
        except Exception: evidence={}
        return {'result':result,'evidence':evidence}
    except Exception as exc: raise HTTPException(422,str(exc))
@app.post('/api/cases')
def save(body: SaveCase):
    try:
        case=fu.open_case(body.patient,label=body.label)
        fu.save_case(case)
        return {'case_id':case['case_id'],'decision':case['current_result'].get('decision')}
    except Exception as exc: raise HTTPException(422,str(exc))
@app.post('/api/copilot')
def copilot(body: ChatRequest):
    key=body.api_key or os.getenv('LLM_API_KEY','')
    if not key: raise HTTPException(400,'Enter your API key to use the AI copilot')
    base='https://openrouter.ai/api/v1' if body.provider=='OpenRouter' else 'https://api.mistral.ai/v1'
    try:
        extracted,language=extract_patient_from_text(body.message,key,base,body.model,known=body.known)
        patient=fu.merge_patient_input(body.known,extracted)
        result=apply_rules(patient)
        evidence=retrieve_evidence(result)
        reply=compose_clinical_reply(body.message,result,evidence,language,key,base,body.model)
        return {'reply':reply,'patient':patient,'result':result,'evidence':evidence}
    except Exception as exc: raise HTTPException(422,str(exc))
