from faker import Faker
from detectors import DetectedEntity

fake = Faker("en_US")
Faker.seed(42)


class ReplacementMap:
    """maps original PII text to a consistent fake replacement"""

    def __init__(self):
        self._cache: dict = {}

    def get_or_create(self, entity: DetectedEntity) -> str:
        key = (entity.type, entity.text.strip())
        if key not in self._cache:
            self._cache[key] = self._generate(entity.type, entity.text)
        return self._cache[key]

    def _generate(self, pii_type: str, original: str) -> str:
        if pii_type == "PERSON":
            return fake.name()
        if pii_type == "EMAIL":
            return fake.email()
        if pii_type == "PHONE":
            return fake.phone_number()
        if pii_type == "ORGANIZATION":
            return fake.company()
        if pii_type == "ADDRESS":
            # single-line address to avoid paragraph breaks
            return fake.address().replace("\n", ", ")
        if pii_type == "SSN":
            return fake.ssn()
        if pii_type == "CREDIT_CARD":
            return fake.credit_card_number(card_type=None)
        if pii_type == "DATE_OF_BIRTH":
            return fake.date_of_birth(minimum_age=18, maximum_age=85).strftime("%m/%d/%Y")
        if pii_type == "IP_ADDRESS":
            return fake.ipv4_public()
        # fallback
        return "[REDACTED]"

    def as_dict(self) -> dict:
        return {f"{k[0]}::{k[1]}": v for k, v in self._cache.items()}
