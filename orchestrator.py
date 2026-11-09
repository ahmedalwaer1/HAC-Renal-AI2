"""Orchestrator: AI Agent-based workflow for HAC-Renal AI.

Routes through the LangChain AI Agent which calls deterministic tools.
Falls back to deterministic rules engine if LLM is unavailable.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from agents.llm_agent import evaluate_patient_via_agent


def evaluate_patient(patient_input):
    """Evaluate a patient using the AI Agent (with deterministic fallback)."""
    return evaluate_patient_via_agent(patient_input)