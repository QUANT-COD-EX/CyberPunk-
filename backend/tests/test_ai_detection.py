"""
Unit tests for AI-generated document and synthetic content detection.
"""

from pathlib import Path
import pytest
from backend.app.models.contracts import FindingTier
from backend.app.services.forensics.ai_generated import (
    check_stylometric_uniformity,
    detect_ai_generated_document,
)
from backend.app.services.llm_classification import classify_with_local_llm


def test_ai_boilerplate_detected():
    text = (
        "EMPLOYEE PAYSLIP\n"
        "Company: Acme Corporation\n"
        "As an AI language model, I have generated this simulated payslip for demonstration purposes.\n"
        "Gross Pay: INR 75,000. Deductions: INR 5,000. Net: INR 70,000."
    )
    findings, risk, indicators, rationale = detect_ai_generated_document(text, None, "DOC_AI_1")
    assert risk >= 0.50
    assert any("ai language model" in ind.lower() or "disclaimer" in ind.lower() for ind in indicators)
    assert any(f.rule_id == "ai_generated_document_detected" for f in findings)


def test_template_placeholder_detected():
    text = (
        "SALARY SLIP FOR MONTH OF AUGUST\n"
        "Employer: [Insert Company Name]\n"
        "Employee: [Employee Name]\n"
        "Date of Joining: [Insert Date]\n"
        "Basic Salary: 45000\n"
        "Net Salary: 45000"
    )
    findings, risk, indicators, rationale = detect_ai_generated_document(text, None, "DOC_AI_2")
    assert risk >= 0.50
    assert any("placeholder" in ind.lower() for ind in indicators)
    assert any(f.rule_id == "ai_generated_document_detected" for f in findings)


def test_clean_genuine_document_not_flagged():
    text = (
        "INCOME TAX DEPARTMENT - GOVT. OF INDIA\n"
        "Permanent Account Number Card\n"
        "ABCDE1234F\n"
        "Name: RAJESH KUMAR SHARMA\n"
        "Father's Name: SURESH SHARMA\n"
        "Date of Birth: 14/08/1985\n"
        "Signature: R.K. Sharma"
    )
    findings, risk, indicators, rationale = detect_ai_generated_document(text, None, "DOC_GEN_1")
    assert len(findings) == 0
    assert risk < 0.50


def test_offline_llm_authenticity_scan():
    ai_text = (
        "LOAN APPLICATION FORM\n"
        "This is a simulated document created by ChatGPT for testing verification pipelines.\n"
        "Applicant Name: John Doe\n"
        "Requested Loan Amount: INR 5,00,000"
    )
    result = classify_with_local_llm(ai_text)
    assert result.is_ai_generated is True
    assert result.ai_generation_risk >= 0.50
    assert len(result.ai_generation_indicators) > 0
