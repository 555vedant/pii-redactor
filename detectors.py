import re
import ipaddress
from dataclasses import dataclass
from typing import List

import phonenumbers
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider


@dataclass
class DetectedEntity:
    type: str
    text: str
    start: int
    end: int
    confidence: float


# --- regex patterns ---

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_SSN_RE = re.compile(r"\b(?!000|666|9\d{2})\d{3}[- ](?!00)\d{2}[- ](?!0000)\d{4}\b")

_CC_RE = re.compile(r"\b(?:\d[ \-]?){13,19}\b")

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

# broad date pattern — context window narrows to DOB
_DATE_RE = re.compile(
    r"\b(?:0?[1-9]|1[0-2])[/\-.](?:0?[1-9]|[12]\d|3[01])[/\-.](?:19|20)\d{2}\b"
    r"|\b(?:19|20)\d{2}[/\-.](?:0?[1-9]|1[0-2])[/\-.](?:0?[1-9]|[12]\d|3[01])\b"
)

_DOB_CONTEXT = re.compile(
    r"(?:date of birth|dob|born on|birth date|birthday)[^\w]{0,20}",
    re.IGNORECASE,
)


def _luhn(number: str) -> bool:
    digits = [int(c) for c in number if c.isdigit()]
    if len(digits) < 13:
        return False
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _detect_emails(text: str) -> List[DetectedEntity]:
    results = []
    for m in _EMAIL_RE.finditer(text):
        results.append(DetectedEntity("EMAIL", m.group(), m.start(), m.end(), 0.98))
    return results


def _detect_phones(text: str) -> List[DetectedEntity]:
    results = []
    # US matches
    for match in phonenumbers.PhoneNumberMatcher(text, "US"):
        results.append(DetectedEntity("PHONE", match.raw_string, match.start, match.end, 0.9))
    # IN matches
    for match in phonenumbers.PhoneNumberMatcher(text, "IN"):
        # avoid exact duplicates
        if not any(r.start == match.start and r.end == match.end for r in results):
            results.append(DetectedEntity("PHONE", match.raw_string, match.start, match.end, 0.9))
            
    # fallback for typical IN/Intl formats that might be missed
    for m in re.finditer(r"\b(?:\+91[\-\s]?)?[6-9]\d{9}\b", text):
        if not any(r.start <= m.start() and r.end >= m.end() for r in results):
            results.append(DetectedEntity("PHONE", m.group(), m.start(), m.end(), 0.85))
            
    return results


def _detect_ssn(text: str) -> List[DetectedEntity]:
    results = []
    for m in _SSN_RE.finditer(text):
        results.append(DetectedEntity("SSN", m.group(), m.start(), m.end(), 0.97))
    return results


def _detect_credit_cards(text: str) -> List[DetectedEntity]:
    results = []
    for m in _CC_RE.finditer(text):
        raw = m.group()
        digits_only = re.sub(r"[ \-]", "", raw)
        if _luhn(digits_only):
            results.append(DetectedEntity("CREDIT_CARD", raw, m.start(), m.end(), 0.95))
    return results


def _detect_ips(text: str) -> List[DetectedEntity]:
    results = []
    for m in _IP_RE.finditer(text):
        raw = m.group()
        try:
            addr = ipaddress.ip_address(raw)
            # skip loopback and link-local; real docs rarely have these
            if addr.is_loopback or addr.is_link_local:
                continue
            results.append(DetectedEntity("IP_ADDRESS", raw, m.start(), m.end(), 0.92))
        except ValueError:
            pass
    return results


def _detect_dob(text: str) -> List[DetectedEntity]:
    """dates preceded by DOB-context keywords"""
    results = []
    for ctx in _DOB_CONTEXT.finditer(text):
        # look ahead up to 40 chars after the context keyword
        window = text[ctx.end(): ctx.end() + 40]
        for dm in _DATE_RE.finditer(window):
            abs_start = ctx.end() + dm.start()
            abs_end = ctx.end() + dm.end()
            results.append(DetectedEntity("DATE_OF_BIRTH", dm.group(), abs_start, abs_end, 0.93))
    return results


# --- presidio setup (lazy singleton) ---

_analyzer: AnalyzerEngine = None


def _get_analyzer() -> AnalyzerEngine:
    global _analyzer
    if _analyzer is None:
        config = {"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}]}
        provider = NlpEngineProvider(nlp_configuration=config)
        nlp_engine = provider.create_engine()
        _analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
    return _analyzer


_PRESIDIO_TYPES = {
    "PERSON": "PERSON",
    "ORGANIZATION": "ORGANIZATION",
    "LOCATION": "ADDRESS",
}


_GENERIC_WORDS = {
    "director", "manager", "ceo", "cfo", "coo", "executive", "board of directors",
    "ebitda", "gross domestic product", "corporate office", "registered office",
    "india", "maharashtra", "united states", "private limited", "public limited",
    "chairman", "managing director", "whole-time director", "independent director",
    "rupee", "rupees", "lakh", "crore", "department", "committee", "company",
    "shareholder", "promoter", "customer", "vendor", "act", "rule", "law",
    "state", "government", "national", "international", "ltd", "pvt", "inc",
    "financial", "statement", "report", "policy", "scheme", "fund", "equity",
    "debt", "asset", "liability", "revenue", "expense", "profit", "loss",
    "margin", "tax", "income", "growth", "value", "price", "rate", "index",
    "market", "industry", "sector", "board", "council", "commission", "authority",
    "agency", "bureau", "ministry", "department", "office", "centre", "center",
    "facility", "unit", "plant", "factory", "warehouse", "depot", "store", "shop",
}

def _detect_presidio(text: str) -> List[DetectedEntity]:
    analyzer = _get_analyzer()
    results_raw = analyzer.analyze(
        text=text,
        entities=list(_PRESIDIO_TYPES.keys()),
        language="en",
    )
    results = []
    for r in results_raw:
        if r.entity_type not in _PRESIDIO_TYPES:
            continue
        mapped = _PRESIDIO_TYPES[r.entity_type]
        span = text[r.start: r.end]
        
        # filter generic words (exact or subset if very short)
        span_lower = span.lower().strip()
        if len(span_lower) < 3 or span_lower in _GENERIC_WORDS:
            continue
            
        # generic phrases
        span_lower_words = span_lower.split()
        if any(w in span_lower for w in ["department", "committee", "office", "rupee", "lakh", "crore", "ebitda", "margin", "tax", "income", "growth", "value", "price", "rate", "index", "market", "industry", "sector", "board", "council", "commission", "authority", "agency", "bureau", "ministry", "facility", "unit", "plant", "factory", "warehouse", "depot", "store", "shop", "act", "rule", "law", "state", "government", "national", "international", "financial", "statement", "report", "policy", "scheme", "fund", "equity", "debt", "asset", "liability", "revenue", "expense", "profit", "loss", "shareholder", "promoter", "customer", "vendor", "branch"]):
            continue
            
        if mapped == "ORGANIZATION":
            if len(span_lower_words) == 1 and r.score < 0.9:
                continue
            if any(c.isdigit() for c in span):
                continue
                
        if mapped == "ADDRESS":
            if len(span_lower_words) == 1:
                continue

        # simple context rule: drop low confidence unless capitalized
        if r.score < 0.85:
            if not span.istitle() and not span.isupper():
                continue
                
        # Drop if it doesn't contain at least one uppercase letter (names/orgs usually do)
        if not any(c.isupper() for c in span):
            continue
                
        results.append(DetectedEntity(mapped, span, r.start, r.end, round(r.score, 3)))
    return results


def _resolve_overlaps(entities: List[DetectedEntity]) -> List[DetectedEntity]:
    """keep highest-confidence entity when spans overlap; prefer longer span on tie"""
    entities = sorted(entities, key=lambda e: (-e.confidence, -(e.end - e.start)))
    kept = []
    for e in entities:
        overlaps = any(
            not (e.end <= k.start or e.start >= k.end)
            for k in kept
        )
        if not overlaps:
            kept.append(e)
    return sorted(kept, key=lambda e: e.start)


def detect_all(text: str) -> List[DetectedEntity]:
    entities: List[DetectedEntity] = []
    entities += _detect_emails(text)
    entities += _detect_phones(text)
    entities += _detect_ssn(text)
    entities += _detect_credit_cards(text)
    entities += _detect_ips(text)
    entities += _detect_dob(text)
    entities += _detect_presidio(text)
    return _resolve_overlaps(entities)
