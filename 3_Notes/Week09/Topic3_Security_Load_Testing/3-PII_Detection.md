# Note 3: PII Detection and Data Privacy in LLM Systems

## The PII Problem in LLM Applications

PII (Personally Identifiable Information) flows through LLM systems at every layer:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PII EXPOSURE POINTS                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   USER INPUT                                                    │
│   "My email is john.doe@company.com, please help me with..."    │
│       │                                                         │
│       ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ RAG RETRIEVAL                                           │   │
│   │ Retrieved chunk: "Employee John Doe,                    │   │
│   │ SSN: 123-45-6789, joined on..."                         │   │
│   └─────────────────────────────────────────────────────────┘   │
│       │                                                         │
│       ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ LLM API CALL                                            │   │
│   │ All PII sent to third-party API         ← Data leaves   │   │
│   │ (OpenAI, Anthropic, etc.)                 your control   │   │
│   └─────────────────────────────────────────────────────────┘   │
│       │                                                         │
│       ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ LLM OUTPUT                                              │   │
│   │ "Based on John Doe's record (SSN ending  ← PII in       │   │
│   │ in 6789), the answer is..."                response     │   │
│   └─────────────────────────────────────────────────────────┘   │
│       │                                                         │
│       ▼                                                         │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │ LOGGING                                                 │   │
│   │ Full request/response logged with PII    ← PII in logs  │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Why this matters:**

1. **Compliance** — GDPR, CCPA, HIPAA have strict rules about PII handling
2. **Third-party exposure** — LLM API calls send data to external services
3. **Log retention** — PII in logs creates long-term liability
4. **Data breaches** — Any leak exposes the PII your system processed
5. **Training data** — Some providers may use your data for model training

---

## PII Categories

Not all PII is equal. Understanding categories helps prioritize detection efforts.

### Direct Identifiers

Can identify an individual on their own.

|Type|Examples|Risk Level|
|---|---|---|
|Full name|"John Smith"|High|
|Email address|"john@company.com"|High|
|Phone number|"+1-555-123-4567"|High|
|Social Security Number|"123-45-6789"|Critical|
|Passport/ID number|"AB1234567"|Critical|
|Credit card number|"4532-1234-5678-9012"|Critical|
|Physical address|"123 Main St, City, State 12345"|High|
|IP address|"192.168.1.1"|Medium|

### Quasi-Identifiers

Can identify individuals when combined with other data.

|Type|Examples|Risk When Combined|
|---|---|---|
|Age/Date of birth|"35 years old", "1989-03-15"|High|
|Zip code|"94107"|Medium-High|
|Gender|"Female"|Medium|
|Job title|"Senior Software Engineer at Acme"|Medium|
|Education|"PhD from MIT, 2015"|Medium|
|Ethnicity/Race|"Asian-American"|Medium|

**The combination problem:** Research shows that 87% of Americans can be uniquely identified by zip code + gender + date of birth alone.

### Sensitive Data

Special categories with additional legal protections.

|Type|Regulations|Handling|
|---|---|---|
|Health information|HIPAA (US), GDPR Art. 9|Extra encryption, access controls|
|Financial records|GLBA, PCI-DSS|Never log, minimize retention|
|Biometric data|BIPA (Illinois), GDPR|Explicit consent required|
|Political/religious views|GDPR Art. 9|Generally avoid collecting|
|Credentials/passwords|All|Never store plaintext, never log|

---

## PII Detection Approaches

### Approach 1: Regex Patterns

Fast, reliable for structured PII (emails, SSNs, credit cards). Limited for names and unstructured data.

```python
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class PIIMatch:
    """A detected PII instance."""
    entity_type: str
    start: int
    end: int
    text: str
    confidence: float  # 0.0 to 1.0


# Regex patterns for common PII
# Note: These are simplified patterns. Production systems need more comprehensive coverage.

PII_PATTERNS = {
    "EMAIL": re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    ),
    
    "PHONE_US": re.compile(
        r'\b(?:\+1[-.\s]?)?'  # Optional country code
        r'(?:\(?[0-9]{3}\)?[-.\s]?)?'  # Area code
        r'[0-9]{3}[-.\s]?[0-9]{4}\b'  # Main number
    ),
    
    "SSN": re.compile(
        r'\b(?!000|666|9\d{2})'  # Invalid SSN prefixes
        r'[0-9]{3}[-\s]?'
        r'(?!00)[0-9]{2}[-\s]?'
        r'(?!0000)[0-9]{4}\b'
    ),
    
    "CREDIT_CARD": re.compile(
        r'\b(?:4[0-9]{12}(?:[0-9]{3})?|'  # Visa
        r'5[1-5][0-9]{14}|'  # Mastercard
        r'3[47][0-9]{13}|'  # Amex
        r'6(?:011|5[0-9]{2})[0-9]{12})\b'  # Discover
    ),
    
    "IP_ADDRESS": re.compile(
        r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
    ),
    
    "DATE_OF_BIRTH": re.compile(
        r'\b(?:DOB|Date of Birth|Born|Birthday)[:\s]*'
        r'(?:[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4}|'
        r'[A-Za-z]+ [0-9]{1,2},? [0-9]{4})\b',
        re.IGNORECASE
    ),
    
    # US ZIP codes (5 digit and ZIP+4)
    "ZIP_CODE": re.compile(
        r'\b[0-9]{5}(?:-[0-9]{4})?\b'
    ),
}


def detect_pii_regex(text: str) -> list[PIIMatch]:
    """
    Detect PII using regex patterns.
    
    Pros: Fast, deterministic, no external dependencies
    Cons: Limited to structured patterns, no context awareness
    """
    matches = []
    
    for entity_type, pattern in PII_PATTERNS.items():
        for match in pattern.finditer(text):
            matches.append(PIIMatch(
                entity_type=entity_type,
                start=match.start(),
                end=match.end(),
                text=match.group(),
                confidence=0.9,  # Regex matches are high confidence
            ))
    
    return matches


# Validation functions for reducing false positives
def validate_credit_card(number: str) -> bool:
    """Luhn algorithm for credit card validation."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13:
        return False
    
    # Luhn checksum
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    
    return checksum % 10 == 0


def validate_ssn(ssn: str) -> bool:
    """Basic SSN validation (format only, not existence)."""
    digits = ''.join(c for c in ssn if c.isdigit())
    if len(digits) != 9:
        return False
    
    # Invalid area numbers
    area = int(digits[:3])
    if area == 0 or area == 666 or area >= 900:
        return False
    
    # Invalid group numbers
    group = int(digits[3:5])
    if group == 0:
        return False
    
    # Invalid serial numbers
    serial = int(digits[5:])
    if serial == 0:
        return False
    
    return True
```

### Approach 2: Named Entity Recognition (NER)

Better for names, locations, organizations. Requires ML models.

```python
# spaCy NER for PII detection
# Install: pip install spacy
# Download model: python -m spacy download en_core_web_lg

import spacy

# Load model once at startup
nlp = spacy.load("en_core_web_lg")


def detect_pii_ner(text: str) -> list[PIIMatch]:
    """
    Detect PII using spaCy NER.
    
    Detects: PERSON, ORG, GPE (locations), DATE, MONEY, etc.
    
    Pros: Handles unstructured data (names, locations)
    Cons: Slower, requires model, not 100% accurate
    """
    doc = nlp(text)
    matches = []
    
    # Map spaCy entity types to PII categories
    pii_entity_types = {
        "PERSON": "NAME",
        "GPE": "LOCATION",  # Geopolitical entity (cities, countries)
        "LOC": "LOCATION",  # Non-GPE locations
        "ORG": "ORGANIZATION",
        "DATE": "DATE",
        "MONEY": "FINANCIAL",
        "CARDINAL": None,  # Numbers — usually not PII
    }
    
    for ent in doc.ents:
        pii_type = pii_entity_types.get(ent.label_)
        if pii_type:
            matches.append(PIIMatch(
                entity_type=pii_type,
                start=ent.start_char,
                end=ent.end_char,
                text=ent.text,
                confidence=0.7,  # NER is less certain than regex
            ))
    
    return matches
```

### Approach 3: Microsoft Presidio

Production-grade PII detection combining regex, NER, and context awareness.

```python
# Microsoft Presidio — production-grade PII detection
# Install: pip install presidio-analyzer presidio-anonymizer
# Download spaCy model: python -m spacy download en_core_web_lg

# Docs: https://microsoft.github.io/presidio/
# Current version: 2.2.362 (as of early 2026)

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig


# Initialize engines (do this once at startup)
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()


def detect_pii_presidio(
    text: str,
    language: str = "en",
    score_threshold: float = 0.5,
) -> list[RecognizerResult]:
    """
    Detect PII using Microsoft Presidio.
    
    Built-in recognizers include:
    - CREDIT_CARD, CRYPTO, EMAIL_ADDRESS, IBAN_CODE
    - IP_ADDRESS, PHONE_NUMBER, URL
    - US_SSN, US_PASSPORT, US_DRIVER_LICENSE
    - UK_NHS, SG_NRIC_FIN (country-specific IDs)
    - PERSON, LOCATION, ORGANIZATION (via NER)
    - DATE_TIME, NRP (nationality/religion/politics)
    
    Args:
        text: Input text to analyze
        language: Language code (en, es, de, etc.)
        score_threshold: Minimum confidence score (0.0-1.0)
    
    Returns:
        List of RecognizerResult with entity_type, start, end, score
    """
    results = analyzer.analyze(
        text=text,
        language=language,
        score_threshold=score_threshold,
    )
    
    return results


def anonymize_text_presidio(
    text: str,
    analyzer_results: list[RecognizerResult],
    operators: dict = None,
) -> str:
    """
    Anonymize detected PII using Presidio Anonymizer.
    
    Default behavior: Replace PII with entity type (e.g., <EMAIL_ADDRESS>)
    
    Args:
        text: Original text
        analyzer_results: Results from analyzer.analyze()
        operators: Custom anonymization operators per entity type
    
    Returns:
        Anonymized text
    """
    if operators is None:
        # Default: replace with entity type
        operators = {}
    
    result = anonymizer.anonymize(
        text=text,
        analyzer_results=analyzer_results,
        operators=operators,
    )
    
    return result.text


# Example with custom operators
def anonymize_with_custom_operators(text: str) -> str:
    """
    Anonymize with different strategies per entity type.
    """
    # Detect PII
    results = analyzer.analyze(text=text, language="en")
    
    # Define custom operators
    operators = {
        # Redact completely
        "CREDIT_CARD": OperatorConfig("redact"),
        "US_SSN": OperatorConfig("redact"),
        
        # Replace with placeholder
        "EMAIL_ADDRESS": OperatorConfig(
            "replace",
            {"new_value": "[EMAIL]"}
        ),
        "PHONE_NUMBER": OperatorConfig(
            "replace",
            {"new_value": "[PHONE]"}
        ),
        
        # Mask partially (show last 4 digits)
        "US_BANK_NUMBER": OperatorConfig(
            "mask",
            {
                "type": "mask",
                "masking_char": "*",
                "chars_to_mask": 12,
                "from_end": False,
            }
        ),
        
        # Hash for pseudonymization (reversible with key)
        "PERSON": OperatorConfig(
            "hash",
            {"hash_type": "sha256"}
        ),
    }
    
    # Anonymize
    result = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators,
    )
    
    return result.text


# Example: Custom recognizer for domain-specific PII
from presidio_analyzer import Pattern, PatternRecognizer

def create_custom_recognizer():
    """
    Create a custom recognizer for domain-specific PII.
    
    Example: Employee IDs with format EMP-XXXXXX
    """
    employee_id_pattern = Pattern(
        name="employee_id_pattern",
        regex=r"\bEMP-[0-9]{6}\b",
        score=0.9,  # High confidence for exact pattern
    )
    
    employee_id_recognizer = PatternRecognizer(
        supported_entity="EMPLOYEE_ID",
        patterns=[employee_id_pattern],
        context=["employee", "staff", "worker", "id"],  # Context words boost score
    )
    
    return employee_id_recognizer


# Add custom recognizer to analyzer
def setup_analyzer_with_custom_recognizers():
    """Set up analyzer with custom recognizers."""
    analyzer = AnalyzerEngine()
    
    # Add custom recognizer
    employee_recognizer = create_custom_recognizer()
    analyzer.registry.add_recognizer(employee_recognizer)
    
    return analyzer
```

---

## PII Handling Strategies

Once detected, what do you do with PII?

### Strategy 1: Redaction

Replace PII with a generic placeholder. Simple, irreversible.

```python
def redact_pii(
    text: str,
    detections: list[PIIMatch],
    placeholder: str = "[REDACTED]",
) -> str:
    """
    Redact PII with placeholder.
    
    Pros: Simple, guaranteed to remove PII
    Cons: Loss of information, can break context
    """
    # Sort by position (reverse) to maintain indices during replacement
    sorted_detections = sorted(detections, key=lambda x: x.start, reverse=True)
    
    result = text
    for detection in sorted_detections:
        result = result[:detection.start] + placeholder + result[detection.end:]
    
    return result


def redact_pii_typed(
    text: str,
    detections: list[PIIMatch],
) -> str:
    """
    Redact with entity-type placeholders.
    
    Example: "john@email.com" → "[EMAIL]"
    """
    sorted_detections = sorted(detections, key=lambda x: x.start, reverse=True)
    
    result = text
    for detection in sorted_detections:
        placeholder = f"[{detection.entity_type}]"
        result = result[:detection.start] + placeholder + result[detection.end:]
    
    return result
```

### Strategy 2: Masking

Partially hide PII while preserving structure. Useful for debugging.

```python
def mask_pii(
    text: str,
    detections: list[PIIMatch],
    mask_char: str = "*",
    visible_chars: int = 4,  # Show last N characters
) -> str:
    """
    Mask PII while preserving partial information.
    
    Example: "john.doe@email.com" → "***********il.com"
    """
    sorted_detections = sorted(detections, key=lambda x: x.start, reverse=True)
    
    result = text
    for detection in sorted_detections:
        original = detection.text
        if len(original) > visible_chars:
            masked = mask_char * (len(original) - visible_chars) + original[-visible_chars:]
        else:
            masked = mask_char * len(original)
        
        result = result[:detection.start] + masked + result[detection.end:]
    
    return result
```

### Strategy 3: Pseudonymization (Tokenization)

Replace with consistent fake values. Reversible with a mapping table.

```python
import hashlib
from typing import Optional


class Pseudonymizer:
    """
    Replace PII with consistent pseudonyms.
    
    Same input always produces same output (for consistency).
    Reversible if you keep the mapping table.
    
    Use cases:
    - Testing with realistic data
    - Analytics while preserving privacy
    - Sharing data with third parties
    """
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self._reverse_map: dict[str, str] = {}  # pseudonym -> original
    
    def _generate_pseudonym(
        self,
        original: str,
        entity_type: str,
    ) -> str:
        """Generate consistent pseudonym for a value."""
        # Hash original + secret for consistency
        hash_input = f"{self.secret_key}:{entity_type}:{original}"
        hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        
        return f"{entity_type}_{hash_digest}"
    
    def pseudonymize(
        self,
        text: str,
        detections: list[PIIMatch],
        store_reverse_mapping: bool = True,
    ) -> str:
        """
        Replace PII with pseudonyms.
        
        Args:
            text: Original text
            detections: PII detections
            store_reverse_mapping: Whether to store original values for reversal
        
        Returns:
            Text with PII replaced by pseudonyms
        """
        sorted_detections = sorted(detections, key=lambda x: x.start, reverse=True)
        
        result = text
        for detection in sorted_detections:
            pseudonym = self._generate_pseudonym(
                detection.text,
                detection.entity_type,
            )
            
            if store_reverse_mapping:
                self._reverse_map[pseudonym] = detection.text
            
            result = result[:detection.start] + pseudonym + result[detection.end:]
        
        return result
    
    def reverse(self, pseudonymized_text: str) -> str:
        """
        Reverse pseudonymization using stored mapping.
        
        Only works if store_reverse_mapping was True during pseudonymization.
        """
        result = pseudonymized_text
        for pseudonym, original in self._reverse_map.items():
            result = result.replace(pseudonym, original)
        return result
    
    def export_mapping(self) -> dict[str, str]:
        """Export mapping for storage/backup."""
        return dict(self._reverse_map)
    
    def import_mapping(self, mapping: dict[str, str]) -> None:
        """Import mapping from storage."""
        self._reverse_map.update(mapping)
```

### Strategy 4: Synthetic Data Replacement

Replace with realistic fake data. Best for testing and demos.

```python
# Faker for generating realistic fake data
# Install: pip install faker

from faker import Faker

fake = Faker()


class SyntheticReplacer:
    """
    Replace PII with realistic synthetic data.
    
    Maintains consistency: same input produces same fake output.
    """
    
    def __init__(self, seed: int = 42):
        self.fake = Faker()
        self.fake.seed_instance(seed)
        self._cache: dict[str, str] = {}  # original -> synthetic
    
    def _generate_synthetic(
        self,
        original: str,
        entity_type: str,
    ) -> str:
        """Generate synthetic replacement for entity type."""
        cache_key = f"{entity_type}:{original}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        generators = {
            "EMAIL": self.fake.email,
            "PHONE": self.fake.phone_number,
            "NAME": self.fake.name,
            "PERSON": self.fake.name,
            "ADDRESS": self.fake.address,
            "LOCATION": self.fake.city,
            "SSN": lambda: self.fake.ssn(),
            "CREDIT_CARD": lambda: self.fake.credit_card_number(),
            "DATE": lambda: self.fake.date(),
            "ORGANIZATION": self.fake.company,
        }
        
        generator = generators.get(entity_type, lambda: f"[{entity_type}]")
        synthetic = generator()
        
        self._cache[cache_key] = synthetic
        return synthetic
    
    def replace(
        self,
        text: str,
        detections: list[PIIMatch],
    ) -> str:
        """Replace PII with synthetic data."""
        sorted_detections = sorted(detections, key=lambda x: x.start, reverse=True)
        
        result = text
        for detection in sorted_detections:
            synthetic = self._generate_synthetic(
                detection.text,
                detection.entity_type,
            )
            result = result[:detection.start] + synthetic + result[detection.end:]
        
        return result
```

---

## Where to Apply PII Handling

### At Input (Before LLM API Call)

**Goal:** Prevent PII from reaching third-party APIs.

```python
import logging

logger = logging.getLogger(__name__)


class PIIProtectedLLMClient:
    """
    LLM client that redacts PII before sending to API.
    
    Critical for:
    - Compliance (GDPR, CCPA)
    - Preventing data from being used for training
    - Reducing exposure in case of API provider breach
    """
    
    def __init__(
        self,
        llm_client,  # Your actual LLM client
        anonymize_input: bool = True,
        anonymize_output: bool = True,
        log_pii_detections: bool = True,
    ):
        self.llm_client = llm_client
        self.anonymize_input = anonymize_input
        self.anonymize_output = anonymize_output
        self.log_pii_detections = log_pii_detections
        
        # Initialize Presidio
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
    
    def _anonymize_text(self, text: str) -> tuple[str, list]:
        """Anonymize text and return (anonymized_text, detections)."""
        results = self.analyzer.analyze(text=text, language="en")
        
        if results:
            anonymized = self.anonymizer.anonymize(
                text=text,
                analyzer_results=results,
            )
            return anonymized.text, results
        
        return text, []
    
    def chat(
        self,
        messages: list[dict],
        **kwargs,
    ) -> str:
        """
        Send chat request with PII protection.
        """
        processed_messages = []
        all_detections = []
        
        # Anonymize user messages
        for msg in messages:
            if msg["role"] == "user" and self.anonymize_input:
                anonymized_content, detections = self._anonymize_text(msg["content"])
                all_detections.extend(detections)
                processed_messages.append({
                    "role": msg["role"],
                    "content": anonymized_content,
                })
            else:
                processed_messages.append(msg)
        
        # Log detections (without PII values)
        if self.log_pii_detections and all_detections:
            self._log_detections(all_detections)
        
        # Call LLM with anonymized messages
        response = self.llm_client.chat(processed_messages, **kwargs)
        
        # Anonymize output if needed
        if self.anonymize_output:
            response, output_detections = self._anonymize_text(response)
            if output_detections:
                self._log_detections(output_detections, location="output")
        
        return response
    
    def _log_detections(
        self,
        detections: list,
        location: str = "input",
    ) -> None:
        """Log PII detections without logging the actual PII."""
        detection_summary = [
            {"type": d.entity_type, "score": d.score}
            for d in detections
        ]
        logger.info(
            f"PII detected in {location}",
            extra={"detections": detection_summary},
        )
```

### At RAG Retrieval

**Goal:** Handle PII in retrieved documents.

```python
class PIIAwareRetriever:
    """
    Retriever that handles PII in retrieved chunks.
    
    Options:
    1. Filter out chunks with sensitive PII
    2. Redact PII in chunks before returning
    3. Flag chunks for human review
    """
    
    def __init__(
        self,
        base_retriever,
        pii_strategy: str = "redact",  # "redact", "filter", "flag"
        sensitive_types: set = None,
    ):
        self.base_retriever = base_retriever
        self.pii_strategy = pii_strategy
        self.sensitive_types = sensitive_types or {
            "US_SSN", "CREDIT_CARD", "US_BANK_NUMBER",
            "MEDICAL_LICENSE", "US_PASSPORT",
        }
        
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Retrieve documents with PII handling.
        """
        # Get raw results
        results = self.base_retriever.retrieve(query, top_k=top_k * 2)  # Over-fetch for filtering
        
        processed_results = []
        
        for result in results:
            # Detect PII in chunk
            detections = self.analyzer.analyze(
                text=result["content"],
                language="en",
            )
            
            sensitive_detections = [
                d for d in detections
                if d.entity_type in self.sensitive_types
            ]
            
            if self.pii_strategy == "filter":
                # Skip chunks with sensitive PII
                if not sensitive_detections:
                    processed_results.append(result)
            
            elif self.pii_strategy == "redact":
                # Redact PII in chunk
                if detections:
                    result["content"] = self.anonymizer.anonymize(
                        text=result["content"],
                        analyzer_results=detections,
                    ).text
                    result["pii_redacted"] = True
                processed_results.append(result)
            
            elif self.pii_strategy == "flag":
                # Include but flag sensitive chunks
                result["has_sensitive_pii"] = bool(sensitive_detections)
                result["pii_types"] = [d.entity_type for d in detections]
                processed_results.append(result)
            
            if len(processed_results) >= top_k:
                break
        
        return processed_results[:top_k]
```

### At Logging

**Goal:** Never persist PII in logs.

```python
import logging
import json
from typing import Any


class PIIRedactingFormatter(logging.Formatter):
    """
    Logging formatter that redacts PII from log messages.
    
    CRITICAL: Logs are often retained for months/years.
    PII in logs creates long-term compliance liability.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.analyzer = AnalyzerEngine()
    
    def format(self, record: logging.LogRecord) -> str:
        # Redact message
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        
        # Redact args
        if record.args:
            record.args = tuple(
                self._redact(arg) if isinstance(arg, str) else arg
                for arg in record.args
            )
        
        # Redact extra fields
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if isinstance(value, str) and key not in (
                    'name', 'levelname', 'pathname', 'filename',
                    'module', 'funcName', 'lineno', 'msg',
                ):
                    record.__dict__[key] = self._redact(value)
        
        return super().format(record)
    
    def _redact(self, text: str) -> str:
        """Redact PII from text."""
        if not text:
            return text
        
        results = self.analyzer.analyze(text=text, language="en")
        
        if not results:
            return text
        
        # Sort by position (reverse) for replacement
        sorted_results = sorted(results, key=lambda x: x.start, reverse=True)
        
        redacted = text
        for result in sorted_results:
            placeholder = f"[{result.entity_type}]"
            redacted = redacted[:result.start] + placeholder + redacted[result.end:]
        
        return redacted


# Setup PII-safe logging
def setup_pii_safe_logging():
    """Configure logging to automatically redact PII."""
    handler = logging.StreamHandler()
    handler.setFormatter(PIIRedactingFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
```

---

## The Utility vs Privacy Trade-off

Heavy redaction breaks functionality. Light redaction leaks data. Finding the balance requires understanding your specific context.

### Context-Aware Redaction

```python
class ContextAwarePIIHandler:
    """
    Apply different PII handling based on context.
    
    Not all PII needs the same treatment:
    - SSN in any context → always redact
    - Name in customer service context → might need to keep
    - Email in internal tool → might be fine
    - Email going to external API → redact
    """
    
    def __init__(self):
        self.analyzer = AnalyzerEngine()
        self.anonymizer = AnonymizerEngine()
    
    def handle_pii(
        self,
        text: str,
        context: str,  # "internal", "external_api", "logging", "user_display"
        allowed_entity_types: set = None,
    ) -> str:
        """
        Handle PII based on context.
        
        Args:
            text: Input text
            context: Where this text will be used
            allowed_entity_types: Entity types to NOT redact
        """
        results = self.analyzer.analyze(text=text, language="en")
        
        if not results:
            return text
        
        # Define what's always redacted regardless of context
        always_redact = {
            "US_SSN", "CREDIT_CARD", "US_BANK_NUMBER",
            "CRYPTO", "US_PASSPORT", "MEDICAL_LICENSE",
        }
        
        # Define context-specific rules
        context_rules = {
            "internal": {
                # Internal tools can see most PII except critical
                "redact": always_redact,
            },
            "external_api": {
                # External APIs see nothing
                "redact": always_redact | {
                    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
                    "LOCATION", "ORGANIZATION",
                },
            },
            "logging": {
                # Logs see nothing
                "redact": always_redact | {
                    "PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
                    "LOCATION", "DATE_TIME", "IP_ADDRESS",
                },
            },
            "user_display": {
                # Users can see their own data, but critical stuff is masked
                "redact": always_redact,
            },
        }
        
        rules = context_rules.get(context, context_rules["external_api"])
        to_redact = rules["redact"]
        
        # Override with allowed types
        if allowed_entity_types:
            to_redact = to_redact - allowed_entity_types
        
        # Filter results to only those we're redacting
        results_to_redact = [r for r in results if r.entity_type in to_redact]
        
        if not results_to_redact:
            return text
        
        return self.anonymizer.anonymize(
            text=text,
            analyzer_results=results_to_redact,
        ).text
```

### Balancing Precision and Recall

```
┌─────────────────────────────────────────────────────────────────┐
│                    DETECTION TRADE-OFFS                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   HIGH RECALL (Catch Everything)                                │
│   ├── Low threshold, aggressive patterns                        │
│   ├── Pros: Minimal PII leakage                                 │
│   └── Cons: Many false positives, broken functionality          │
│       Example: "John" redacted even when it's not a name        │
│                                                                 │
│   HIGH PRECISION (Only Confident Detections)                    │
│   ├── High threshold, strict patterns                           │
│   ├── Pros: Fewer false positives, better UX                    │
│   └── Cons: Some PII may slip through                           │
│       Example: Unusual name formats not detected                │
│                                                                 │
│   RECOMMENDATION BY USE CASE:                                   │
│   ├── Healthcare (HIPAA): High recall, accept false positives   │
│   ├── Customer service: Balanced, tune based on feedback        │
│   ├── Internal analytics: High precision, manual review         │
│   └── External API calls: High recall, safety first             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Compliance Considerations

### Key Regulations

|Regulation|Scope|Key Requirements|
|---|---|---|
|**GDPR**|EU residents|Consent, right to deletion, data minimization, breach notification|
|**CCPA/CPRA**|California residents|Right to know, delete, opt-out of sale|
|**HIPAA**|US healthcare|PHI protection, access controls, audit trails|
|**PCI-DSS**|Payment cards|Never store CVV, encrypt card numbers, access logging|

### Right to Deletion

**The hard problem:** If a user requests deletion, can you actually delete their data?

```python
class DataDeletionHandler:
    """
    Handle right-to-deletion requests.
    
    GDPR Article 17: Users can request deletion of their personal data.
    
    Challenges in LLM systems:
    1. Data in vector store embeddings — can you remove specific chunks?
    2. Data in conversation logs — can you identify all user data?
    3. Data sent to third-party APIs — already out of your control
    4. Data in model weights — if used for fine-tuning, can't remove
    """
    
    def __init__(
        self,
        vector_store,
        conversation_store,
        user_data_store,
    ):
        self.vector_store = vector_store
        self.conversation_store = conversation_store
        self.user_data_store = user_data_store
    
    def process_deletion_request(
        self,
        user_id: str,
        request_id: str,
    ) -> dict:
        """
        Process a data deletion request.
        
        Returns summary of what was deleted and what couldn't be deleted.
        """
        results = {
            "request_id": request_id,
            "user_id": user_id,
            "deleted": [],
            "not_deletable": [],
            "requires_manual_review": [],
        }
        
        # 1. Delete from conversation store
        try:
            deleted_conversations = self.conversation_store.delete_by_user(user_id)
            results["deleted"].append({
                "store": "conversations",
                "count": deleted_conversations,
            })
        except Exception as e:
            results["not_deletable"].append({
                "store": "conversations",
                "reason": str(e),
            })
        
        # 2. Delete from vector store (if we can identify user's chunks)
        try:
            # This assumes you tagged chunks with user_id
            deleted_chunks = self.vector_store.delete_by_metadata(
                filter={"user_id": user_id}
            )
            results["deleted"].append({
                "store": "vector_store",
                "count": deleted_chunks,
            })
        except Exception as e:
            results["requires_manual_review"].append({
                "store": "vector_store",
                "reason": "Cannot automatically identify user's chunks",
            })
        
        # 3. Delete from user data store
        try:
            self.user_data_store.delete_user(user_id)
            results["deleted"].append({
                "store": "user_data",
                "count": 1,
            })
        except Exception as e:
            results["not_deletable"].append({
                "store": "user_data",
                "reason": str(e),
            })
        
        # 4. Note what can't be deleted
        results["not_deletable"].append({
            "store": "third_party_api_logs",
            "reason": "Data sent to OpenAI/Anthropic APIs cannot be recalled",
        })
        
        return results
```

### Data Retention Policies

```python
from datetime import datetime, timedelta
from enum import Enum


class RetentionPolicy(Enum):
    """Data retention periods by category."""
    
    CONVERSATION_LOGS = timedelta(days=30)
    USER_PREFERENCES = timedelta(days=365)
    ANALYTICS_AGGREGATED = timedelta(days=730)  # 2 years
    AUDIT_LOGS = timedelta(days=2555)  # 7 years (legal requirement)
    PII_IN_LOGS = timedelta(days=0)  # Never retain


class DataRetentionManager:
    """
    Manage data retention policies.
    
    Automatic cleanup of data past retention period.
    """
    
    def __init__(self, storage_client):
        self.storage = storage_client
    
    def cleanup_expired_data(self) -> dict:
        """Run cleanup for all data types."""
        results = {}
        
        for policy in RetentionPolicy:
            if policy.value.days == 0:
                continue  # Skip "never retain" — shouldn't exist anyway
            
            cutoff = datetime.now() - policy.value
            deleted_count = self.storage.delete_older_than(
                data_type=policy.name,
                cutoff_date=cutoff,
            )
            results[policy.name] = deleted_count
        
        return results
```

---

## Key Takeaways

1. **PII flows through every layer** — Inputs, retrieved context, outputs, and logs all contain PII exposure risks.
    
2. **Use Presidio for production** — Microsoft's open-source library combines regex, NER, and context awareness. Don't reinvent the wheel.
    
3. **Match strategy to context** — Redaction for external APIs, pseudonymization for analytics, masking for internal tools.
    
4. **Redact before logging** — Logs persist for years. PII in logs is long-term liability.
    
5. **Consider retrieval-time filtering** — For RAG systems, decide whether to filter, redact, or flag chunks with sensitive PII.
    
6. **Compliance requires architecture** — Right to deletion is hard if you didn't design for it. Tag user data from the start.
    
7. **Balance precision and recall** — Healthcare needs high recall (catch everything). Customer service needs balance (don't break UX).
    

---

## What's Next

- **Note 4** covers load testing fundamentals — understanding your system's capacity
- **Note 5** covers the SecurityLayer integration — combining all security measures

---

## References

- Microsoft Presidio Documentation: https://microsoft.github.io/presidio/
- Presidio GitHub: https://github.com/microsoft/presidio (v2.2.362)
- Presidio-Analyzer PyPI: https://pypi.org/project/presidio-analyzer/
- spaCy NER Models: https://spacy.io/models
- GDPR Article 17 (Right to Erasure): https://gdpr-info.eu/art-17-gdpr/
- HIPAA Privacy Rule: https://www.hhs.gov/hipaa/for-professionals/privacy/