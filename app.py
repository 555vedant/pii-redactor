import io
import json
import os
import tempfile

import streamlit as st

from redactor import redact

st.set_page_config(
    page_title="PII Redactor",
    layout="centered",
)

# --- minimal custom CSS ---
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .block-container {
        max-width: 780px;
        padding-top: 2.5rem;
    }

    h1 {
        font-size: 1.6rem;
        font-weight: 600;
        letter-spacing: -0.3px;
        margin-bottom: 0.25rem;
    }

    .sub {
        color: #6b7280;
        font-size: 0.9rem;
        margin-bottom: 2rem;
    }

    .pii-table th {
        text-align: left;
        font-weight: 500;
        color: #374151;
        padding: 6px 12px;
        background: #f3f4f6;
        border-bottom: 1px solid #e5e7eb;
    }

    .pii-table td {
        padding: 6px 12px;
        border-bottom: 1px solid #f3f4f6;
        font-size: 0.9rem;
    }

    .pii-table tr:last-child td {
        border-bottom: none;
    }

    .count-badge {
        display: inline-block;
        background: #1e293b;
        color: #f8fafc;
        border-radius: 4px;
        padding: 1px 8px;
        font-size: 0.8rem;
        font-weight: 500;
    }

    .stDownloadButton button {
        background-color: #1e293b !important;
        color: #f8fafc !important;
        border: none !important;
        font-weight: 500 !important;
    }

    .stDownloadButton button:hover {
        background-color: #334155 !important;
    }

    div[data-testid="stFileUploader"] {
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 0.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- header ---
st.markdown("# PII Redactor")
st.markdown('<p class="sub">Upload a .docx file. The tool detects and replaces PII with realistic fake values.</p>', unsafe_allow_html=True)

st.divider()

# --- upload ---
uploaded = st.file_uploader("Upload a DOCX file", type=["docx"], label_visibility="collapsed")

if uploaded:
    st.markdown(f"**File:** `{uploaded.name}`  —  {round(len(uploaded.getvalue()) / 1024, 1)} KB")

    if st.button("Redact Document", type="primary", use_container_width=False):
        with st.spinner("Detecting PII and generating redacted document…"):
            # write upload to a temp file
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_in:
                tmp_in.write(uploaded.getvalue())
                tmp_in_path = tmp_in.name

            tmp_out_path = tmp_in_path.replace(".docx", "_redacted.docx")

            try:
                counts, entities = redact(tmp_in_path, tmp_out_path)

                with open(tmp_out_path, "rb") as f:
                    redacted_bytes = f.read()

                st.session_state["counts"] = counts
                st.session_state["entities"] = entities
                st.session_state["redacted_bytes"] = redacted_bytes
                st.session_state["filename"] = uploaded.name.replace(".docx", "_redacted.docx")

            except Exception as exc:
                st.error(f"Processing failed: {exc}")
                raise
            finally:
                try:
                    os.unlink(tmp_in_path)
                    os.unlink(tmp_out_path)
                except OSError:
                    pass

# --- results ---
if st.session_state.get("redacted_bytes"):
    st.divider()
    st.markdown("### Results")

    counts = st.session_state["counts"]
    entities = st.session_state["entities"]
    total = sum(counts.values())

    st.success(f"Successfully processed document. {total} PII instance(s) detected and replaced.")

    # counts table
    label_map = {
        "PERSON": "Full Name",
        "EMAIL": "Email Address",
        "PHONE": "Phone Number",
        "ORGANIZATION": "Organization",
        "ADDRESS": "Physical Address",
        "SSN": "Social Security Number",
        "CREDIT_CARD": "Credit Card Number",
        "DATE_OF_BIRTH": "Date of Birth",
        "IP_ADDRESS": "IP Address",
    }

    rows = ""
    for ptype, cnt in sorted(counts.items(), key=lambda x: -x[1]):
        label = label_map.get(ptype, ptype)
        rows += f"<tr><td>{label}</td><td><span class='count-badge'>{cnt}</span></td></tr>"

    st.markdown(
        f"""
        <table class="pii-table" style="width:100%;border-collapse:collapse;margin-top:0.75rem;">
          <thead><tr><th>Category</th><th>Count</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")

    # download button
    st.download_button(
        label="Download Redacted DOCX",
        data=st.session_state["redacted_bytes"],
        file_name=st.session_state["filename"],
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    # bonus: detection report
    with st.expander("Detection Report (JSON)"):
        report = [
            {
                "type": e.type,
                "original_text": e.text,
                "start": e.start,
                "end": e.end,
                "confidence": e.confidence,
            }
            for e in entities
        ]
        st.code(json.dumps(report, indent=2), language="json")
