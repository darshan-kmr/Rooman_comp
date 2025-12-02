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

load_dotenv()

os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

traced_client = wrap_gemini(genai)

MODEL = "gemini-2.0-flash"

@traceable
def call_gemini(system_prompt: str, user_prompt: str) -> str:
    model = traced_client.GenerativeModel(MODEL, system_instruction=system_prompt)
    resp = model.generate_content(user_prompt)
    return resp.text

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
    minimal docx reader using only stdlib.
    """
    data = uploaded_file.read()
    with ZipFile(BytesIO(data)) as docx_zip:
        xml_content = docx_zip.read("word/document.xml")
    tree = XML(xml_content)

    paragraphs = []
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
    supports: pdf, docx, txt.
    for .doc or unknown types: best-effort utf-8 decode.
    """
    if uploaded_file is None:
        return ""

    name = uploaded_file.name.lower()
    uploaded_file.seek(0)

    if name.endswith(".pdf"):
        return extract_text_from_pdf(uploaded_file)
    elif name.endswith(".docx"):
        return extract_text_from_docx(uploaded_file)
    elif name.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="ignore")
    else:
        try:
            return uploaded_file.read().decode("utf-8", errors="ignore")
        except Exception:
            return ""

SCREENING_SYSTEM_PROMPT = """
you are an expert technical recruiter and hr specialist.
your job:
- evaluate multiple resumes against a single job description.
- score each candidate from 0 to 10 based on fit.
- highlight strengths, concerns, and overall suitability.
rules:
- always consider only the given job description.
- penalize resumes that are very generic or unrelated.
- be fair and explain reasoning briefly.
output format (exactly this structure):
1. summary table:
   - a markdown table with columns:
     [candidate id, fit score (0-10), verdict]
2. detailed breakdown per candidate:
   for each candidate:
   - candidate id: x
   - fit score: x/10
   - summary: ...
   - strengths:
     - ...
   - concerns:
     - ...
   - verdict (hire / strong maybe / maybe / reject):
     - ...
3. final ranking:
   - list candidates from best to worst with score.
"""

def build_screening_prompt(job_description: str, candidates: list[str]) -> str:
    text = [
        "job description:\n",
        job_description.strip(),
        "\n\ncandidates:\n",
    ]
    for idx, cv in enumerate(candidates, start=1):
        text.append(f"\n---\ncandidate {idx} resume:\n{cv.strip()}\n")
    return "".join(text)

st.set_page_config(
    page_title="Resume Screening Agent",
    page_icon="",
    layout="wide",
)

st.title("AI Resume Screening Agent")
st.write(
    "Upload a job description and multiple resumes (PDF / DOCX / TXT / text) to get AI-based ranking and feedback."
)

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

resolved_jd_text = jd_text.strip()
if jd_file is not None:
    file_jd_text = extract_text_from_file(jd_file)
    if file_jd_text.strip():
        resolved_jd_text = file_jd_text.strip()

if resolved_jd_text:
    st.caption("Job description text detected.")
else:
    st.caption("⚠ No job description yet. Please paste text or upload a file.")

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

if uploaded_resumes:
    for f in uploaded_resumes:
        text = extract_text_from_file(f)
        if text.strip():
            candidate_texts.append(text.strip())

if extra_text_resumes.strip():
    parts = [p.strip() for p in extra_text_resumes.split("---") if p.strip()]
    candidate_texts.extend(parts)

st.markdown(f"**Detected candidates:** {len(candidate_texts)}")
if len(candidate_texts) == 0:
    st.caption("Upload resumes and/or paste resume text to continue.")

st.markdown("## Run Screening")

if "result_text" not in st.session_state:
    st.session_state["result_text"] = ""

if st.button("Screen Candidates"):
    if not resolved_jd_text:
        st.warning("Please provide the Job Description (either paste or upload).")
    elif len(candidate_texts) == 0:
        st.warning("Please provide at least one candidate resume (file or text).")
    else:
        with st.spinner("Evaluating resumes against the job description..."):
            user_prompt = build_screening_prompt(resolved_jd_text, candidate_texts)
            result_text = call_gemini(SCREENING_SYSTEM_PROMPT, user_prompt)

        st.session_state["result_text"] = result_text

        st.success("Screening complete!")
        st.markdown("## Results")
        st.markdown(result_text)

if st.session_state["result_text"]:
    st.download_button(
        label="Download Results",
        data=st.session_state["result_text"],
        file_name="resume_screening_results.md",
        mime="text/markdown",
    )
