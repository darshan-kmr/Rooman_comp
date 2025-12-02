import os
from io import BytesIO
import streamlit as st
import google.generativeai as genai
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from zipfile import ZipFile
from xml.etree.ElementTree import XML
from langsmith import traceable
from langsmith.wrappers import wrap_gemini

#config
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

traced_client = wrap_gemini(genai)

MODEL = "gemini-2.0-flash"  # or "gemini-2.5-flash-lite"

@traceable
def call_gemini(system_prompt: str, user_prompt: str) -> str:
    model = traced_client.GenerativeModel(MODEL, system_instruction=system_prompt)
    resp = model.generate_content(user_prompt)
    return resp.text

#read files
def extract_text_from_pdf(uploaded_file) -> str:
    reader = PdfReader(uploaded_file)
    text = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            text.append(t)
    return "\n".join(text)

def extract_text_from_docx(uploaded_file) -> str:
    """
    Minimal DOCX reader using only stdlib.
    """
    # uploadedfile is file-like; read its bytes
    data = uploaded_file.read()
    with ZipFile(BytesIO(data)) as docx_zip:
        xml_content = docx_zip.read("word/document.xml")
    tree = XML(xml_content)

    paragraphs = []
    # wordprocessingml namespace
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    for paragraph in tree.iter(f"{ns}p"):
        texts = [
            node.text
            for node in paragraph.iter(f"{ns}t")
            if node.text
        ]
        if texts:
            paragraphs.append("".join(texts))

    return "\n".join(paragraphs)

def extract_text_from_file(uploaded_file) -> str:
    """
    Supports: PDF, DOCX, TXT.
    For .doc or unknown types: best-effort UTF-8 decode.
    """
    if uploaded_file is None:
        return ""

    name = uploaded_file.name.lower()

    # important: reset file pointer if needed
    uploaded_file.seek(0)

    if name.endswith(".pdf"):
        return extract_text_from_pdf(uploaded_file)
    elif name.endswith(".docx"):
        return extract_text_from_docx(uploaded_file)
    elif name.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="ignore")
    else:
        # best-effort for .doc or anything else
        try:
            return uploaded_file.read().decode("utf-8", errors="ignore")
        except Exception:
            return ""


# system prompt

SCREENING_SYSTEM_PROMPT = """
You are an expert technical recruiter and HR specialist.

Your job:
- Evaluate multiple resumes against a single job description.
- Score each candidate from 0 to 10 based on fit.
- Highlight strengths, concerns, and overall suitability.

Rules:
- Always consider only the given job description.
- Penalize resumes that are very generic or unrelated.
- Be fair and explain reasoning briefly.

Output format (exactly this structure):

1. Summary Table:
   - A markdown table with columns:
     [Candidate ID, Fit Score (0-10), Verdict]

2. Detailed Breakdown per Candidate:
   For each candidate:
   - Candidate ID: X
   - Fit Score: X/10
   - Summary: ...
   - Strengths:
     - ...
   - Concerns:
     - ...
   - Verdict (Hire / Strong maybe / Maybe / Reject):
     - ...

3. Final Ranking:
   - List candidates from best to worst with score.
"""


def build_screening_prompt(job_description: str, candidates: list[str]) -> str:
    text = [
        "Job Description:\n",
        job_description.strip(),
        "\n\nCandidates:\n",
    ]
    for idx, cv in enumerate(candidates, start=1):
        text.append(f"\n---\nCandidate {idx} Resume:\n{cv.strip()}\n")
    return "".join(text)

#streamlit ui
st.set_page_config(
    page_title="Resume Screening Agent",
    page_icon="",
    layout="wide",
)

st.title("AI Resume Screening Agent")
st.write(
    "Upload a job description and multiple resumes (PDF / DOCX / TXT / text) to get AI-based ranking and feedback."
)

#job desc 
st.markdown("##Job Description")

col_jd1, col_jd2 = st.columns(2)

with col_jd1:
    jd_text = st.text_area(
        "Paste Job Description (optional if you upload a file)",
        height=200,
        placeholder=(
            "Paste the JD here, e.g., Python backend engineer with Django, "
            "REST APIs, PostgreSQL..."
        ),
        key="jd_text",
    )

with col_jd2:
    jd_file = st.file_uploader(
        "Or upload JD as PDF / DOCX / TXT",
        type=["pdf", "docx", "txt", "doc"],
        key="jd_file",
    )

# resolve jd text: file overrides if present & readable
resolved_jd_text = jd_text.strip()
if jd_file is not None:
    file_jd_text = extract_text_from_file(jd_file)
    if file_jd_text.strip():
        resolved_jd_text = file_jd_text.strip()

if resolved_jd_text:
    st.caption("Job description text detected.")
else:
    st.caption("⚠ No job description yet. Please paste text or upload a file.")

#resume section
st.markdown("## Candidate Resumes")

st.write(
    "You can upload **PDF / DOCX / TXT** files, and also optionally paste raw text "
    "for any candidate."
)

uploaded_resumes = st.file_uploader(
    "Upload one or more resumes",
    type=["pdf", "docx", "txt", "doc"],
    accept_multiple_files=True,
    key="resumes_files",
)

extra_text_resumes = st.text_area(
    "Optional: Paste one or more resumes as text (separate candidates with a line like '---')",
    height=200,
    placeholder="Candidate A...\n...\n---\nCandidate B...\n...",
)

candidate_texts = []

# from files
if uploaded_resumes:
    for f in uploaded_resumes:
        text = extract_text_from_file(f)
        if text.strip():
            candidate_texts.append(text.strip())

# from pasted text (split by ---)
if extra_text_resumes.strip():
    parts = [p.strip() for p in extra_text_resumes.split("---") if p.strip()]
    candidate_texts.extend(parts)

st.markdown(f"**Detected candidates:** {len(candidate_texts)}")
if len(candidate_texts) == 0:
    st.caption("Upload resumes and
