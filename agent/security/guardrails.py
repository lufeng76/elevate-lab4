"""Dual-Boundary Safety Guardrails and Sensitive PII/SPII Redaction Engine.

Implements SDD Section 4.2 (InputSafetyFilter, OutputSafetyFilter) and
Section 4.3 (SPIIMasker) for deterministic, fast-path safety enforcement.
"""
import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# Prompt injection signature patterns
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"system\s+(prompt|instruction|rule)?s?\s*(override|leak|reveal|show|disabled)", re.IGNORECASE),
    re.compile(r"\b(dan(\s+mode)?|do\s+anything\s+now|jailbreak|developer\s+mode)\b", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(unconstrained|an\s+unfiltered|dan\b)", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(rules|constraints|instructions)", re.IGNORECASE),
    re.compile(r"output\s+(your\s+)?initial\s+prompt", re.IGNORECASE),
    re.compile(r"reveal\s+(internal|hidden)\s+(instructions|prompt)", re.IGNORECASE),
    re.compile(r"(curl|wget)\s+.*\|\s*(bash|sh)", re.IGNORECASE),
    re.compile(r"\b(execute\s+this\s+(shell|bash|command)|sudo\s+rm|format\s+c:)\b", re.IGNORECASE),
]

# Toxic or malicious payload indicators
TOXIC_OUTPUT_PATTERNS = [
    re.compile(r"\b(hack\s+into|exfiltrate\s+data|malicious\s+payload)\b", re.IGNORECASE),
    re.compile(r"\b(sudo\s+rm\s+-rf|format\s+c:)\b", re.IGNORECASE),
]

# Sensitive Personal Identifiable Information (SPII) patterns
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
GOV_ID_PATTERN = re.compile(r"\b[A-Z]\d{7}[A-Z]\b")
PHONE_E164_PATTERN = re.compile(r"(?:\+[1-9]\d{6,14}\b|\b[1-9]\d{7,14}\b)")


class SPIIMasker:
    """Masks Personally Identifiable Information and Sensitive Personal Information.

    Conforms to SDD Section 4.3.2 Redaction Taxonomy:
      - Social Security Numbers (SSN) -> [REDACTED_SSN]
      - Credit Cards / Bank Details   -> [REDACTED_FINANCIAL]
      - National / Government ID      -> [REDACTED_GOV_ID]
      - Phone Numbers / Contacts      -> [REDACTED_CONTACT]
    """

    @classmethod
    def mask(cls, text: str) -> str:
        if not text:
            return ""
        masked = SSN_PATTERN.sub("[REDACTED_SSN]", text)
        masked = CREDIT_CARD_PATTERN.sub("[REDACTED_FINANCIAL]", masked)
        masked = GOV_ID_PATTERN.sub("[REDACTED_GOV_ID]", masked)
        masked = PHONE_E164_PATTERN.sub("[REDACTED_CONTACT]", masked)
        return masked


@dataclass
class SafetyResult:
    is_safe: bool
    reason: Optional[str] = None
    sanitized_output: Optional[str] = None
    violation_category: Optional[str] = None


class InputSafetyFilter:
    """Fast-path input boundary guardrail (<150ms budget).

    Scans user queries for adversarial prompt injections, jailbreak tokens,
    and out-of-scope/destructive operations before LLM invocation.
    """

    def __init__(self):
        self.injection_patterns = PROMPT_INJECTION_PATTERNS

    def validate(self, query: str, user_id: str = "anonymous") -> SafetyResult:
        """Scan input query for security violations."""
        if not query or not query.strip():
            return SafetyResult(is_safe=False, reason="Empty query", sanitized_output="Please provide a valid question.")

        # 1. Prompt injection pattern detection
        for pattern in self.injection_patterns:
            if pattern.search(query):
                logger.warning("InputSafetyFilter: Prompt injection detected from user %s: %r", user_id, query)
                return SafetyResult(
                    is_safe=False,
                    reason="Prompt injection pattern matched",
                    sanitized_output="I cannot assist with this request as it violates enterprise security policies.",
                    violation_category="PROMPT_INJECTION",
                )

        return SafetyResult(is_safe=True)


class OutputSafetyFilter:
    """Output boundary safety and data leakage guardrail (<150ms budget).

    Validates generated candidate outputs for toxicity, system prompt leaks,
    and masks sensitive SPII before final streaming to client.
    """

    def __init__(self):
        self.toxic_patterns = TOXIC_OUTPUT_PATTERNS
        self.masker = SPIIMasker()

    def validate(self, response_text: str) -> SafetyResult:
        """Scan and sanitize agent output text."""
        if not response_text:
            return SafetyResult(is_safe=True, sanitized_output="")

        # 1. Toxic / destructive pattern scan
        for pattern in self.toxic_patterns:
            if pattern.search(response_text):
                logger.error("OutputSafetyFilter: Toxic or destructive pattern detected in output.")
                return SafetyResult(
                    is_safe=False,
                    reason="Output safety policy violation",
                    sanitized_output="The response could not be displayed due to content safety policy restrictions.",
                    violation_category="CONTENT_SAFETY",
                )

        # 2. SPII Redaction
        sanitized = self.masker.mask(response_text)

        return SafetyResult(is_safe=True, sanitized_output=sanitized)
