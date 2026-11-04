import re
import uuid
from typing import Dict, List, Tuple
from pydantic import BaseModel, Field

from sentinelforge.utils.audit import audit_logger
from sentinelforge.utils.logging import get_logger

logger = get_logger("sentinelforge.rag.injection_guard")


class InjectionScanResult(BaseModel):
    """Result of prompt injection analysis."""

    is_suspicious: bool
    risk_score: float  # 0.0 to 1.0
    detected_patterns: List[str] = Field(default_factory=list)
    sanitized_text: str


class PromptInjectionGuard:
    """
    Defends against prompt injection, jailbreaks, and delimiter tampering in retrieved documents.
    Treats all external document text as strictly untrusted user-supplied payload.
    """

    # Adversarial patterns commonly found in prompt injection exploits
    INJECTION_PATTERNS = [
        (re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions", re.IGNORECASE), "IGNORE_PREVIOUS_INSTRUCTIONS", 0.9),
        (re.compile(r"disregard\s+(all\s+)?(prior|previous)\s+(prompts|rules)", re.IGNORECASE), "DISREGARD_RULES", 0.9),
        (re.compile(r"you\s+are\s+now\s+(in\s+)?(developer\s+mode|dan\s+mode|unrestricted)", re.IGNORECASE), "JAILBREAK_MODE", 0.95),
        (re.compile(r"system\s*:\s*you\s+must", re.IGNORECASE), "SYSTEM_ROLE_SPOOF", 0.85),
        (re.compile(r"<\s*\|\s*(im_start|im_end|system|user|assistant)\s*\|\s*>", re.IGNORECASE), "SPECIAL_TOKEN_INJECTION", 0.9),
        (re.compile(r"\[\s*(inst|sys|<<SYS>>)\s*\]", re.IGNORECASE), "LLAMA_PROMPT_DELIMITER", 0.8),
        (re.compile(r"(repeat|print|reveal|output)\s+(the\s+)?(system\s+prompt|initial\s+instructions|secret|api\s*key)", re.IGNORECASE), "EXFILTRATION_PROMPT", 0.85),
        (re.compile(r"new\s+system\s+directive\s*:", re.IGNORECASE), "DIRECTIVE_OVERRIDE", 0.85),
    ]

    @classmethod
    def scan_content(cls, text: str) -> InjectionScanResult:
        """
        Scans text for prompt injection signatures and returns risk score and detected patterns.
        """
        detected: List[str] = []
        max_score = 0.0

        for pattern, label, weight in cls.INJECTION_PATTERNS:
            if pattern.search(text):
                detected.append(label)
                if weight > max_score:
                    max_score = weight

        is_suspicious = max_score >= 0.7

        if is_suspicious:
            audit_logger.record_event(
                event_type="PROMPT_INJECTION_DETECTED",
                severity="SECURITY_ALERT",
                details={
                    "risk_score": max_score,
                    "patterns": detected,
                    "preview": text[:120],
                },
                success=False,
            )

        sanitized = cls.neutralize_delimiters(text)

        return InjectionScanResult(
            is_suspicious=is_suspicious,
            risk_score=max_score,
            detected_patterns=detected,
            sanitized_text=sanitized,
        )

    @classmethod
    def neutralize_delimiters(cls, text: str) -> str:
        """
        Escapes XML-like closing tags and special tokens that might simulate system boundaries.
        """
        sanitized = text
        # Neutralize XML tag escapes
        sanitized = re.sub(r"<\s*/\s*untrusted_context_chunk\s*>", "[ESCAPED_TAG]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"<\s*/\s*system\s*>", "[ESCAPED_TAG]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"<\s*\|\s*(im_start|im_end|system)\s*\|\s*>", "[ESCAPED_TOKEN]", sanitized, flags=re.IGNORECASE)
        return sanitized

    @classmethod
    def encapsulate_chunk(
        cls,
        text: str,
        source_file: str,
        citation_ref: str,
    ) -> Tuple[str, InjectionScanResult]:
        """
        Wraps untrusted content into a cryptographic UUID-tagged boundary container.
        Instructs the model explicitly that contents within are untrusted data.
        """
        scan = cls.scan_content(text)
        boundary_id = str(uuid.uuid4())[:8]

        warning_header = ""
        if scan.is_suspicious:
            warning_header = f" [SECURITY WARNING: Untrusted document chunk flagged for potential injection: {','.join(scan.detected_patterns)}]"

        encapsulated = (
            f'<untrusted_context_chunk id="{boundary_id}" source="{source_file}" ref="{citation_ref}"{warning_header}>\n'
            f"{scan.sanitized_text}\n"
            f"</untrusted_context_chunk>"
        )

        return encapsulated, scan

