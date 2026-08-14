# PII Redactor

A local tool for detecting and replacing personally identifiable information in Word documents. Upload a `.docx` file, click Redact, and download a cleaned copy with all PII replaced by realistic fake values.

No external APIs are used. All processing runs on your machine.

## How to run

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
streamlit run app.py
```

Then open `http://localhost:8501` in your browser.

To run the pipeline from the command line:

```bash
python redactor.py input/Scalar.docx output/redacted_output.docx
```

## Detection approach

PII is detected using two methods combined:

**Regex and validation** handles structured fields:
- Email addresses
- Phone numbers (via the `phonenumbers` library and regex fallbacks, supporting US, IN, and Intl formats)
- Social Security Numbers (format + excluded prefixes)
- Credit card numbers (pattern + Luhn checksum)
- IP addresses (validated with the `ipaddress` module; loopback excluded)
- Dates of birth (date pattern + DOB context keyword proximity)

**Presidio with spaCy NER** handles natural language entities:
- Full names (`PERSON`)
- Organizations and company names (`ORGANIZATION`)
- Physical addresses and locations (`LOCATION`)

When detections overlap, the higher-confidence one is kept. Longer spans win on tie.

Repeated occurrences of the same original text always get the same fake replacement.

## Supported PII types

- Full names
- Email addresses
- Phone numbers
- Company and organization names
- Physical and mailing addresses
- Social Security Numbers
- Credit card numbers
- Dates of birth
- IP addresses

## Running tests

```bash
pytest tests/
```

## Evaluation

Annotate `data/ground_truth.json` with the expected spans, then run:

```bash
python evaluate.py input/Scalar.docx
```

This writes `evaluation_report.md` with per-type and overall precision, recall, and F1.

## Architecture

[Architecture diagram will be added here.]

## Known limitations

- Names that appear only as initials or inside heavily formatted table cells may not be detected.
- The DOB detector only fires when a DOB-context keyword appears within 40 characters of a date. Bare date values are not treated as dates of birth.

## Deployment

The app is a plain Streamlit application and can be deployed anywhere Streamlit runs:

```bash
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
```

For Docker, create a standard Python image, copy the project, install requirements, and run the above command. No environment variables or external services are required.
