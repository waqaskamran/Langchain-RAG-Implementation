# ingest_utils.py
import pdfplumber
from langchain_experimental.text_splitter import SemanticChunker
import re

# --- Read PDF ---
def read_pdf(pdf_file):
    text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    return text.strip()

# --- Chunk text ---
def chunk_text(text, embeddings):
    chunker = SemanticChunker(
        embeddings=embeddings,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=90
    )
    return chunker.split_text(text)

# --- Extract metadata ---
def extract_metadata(chunk, idx, doc_type, recruiter_id, applicant_id=None, job_id=None):
    metadata = {
        "chunk_id": idx,
        "doc_type": doc_type,
        "recruiter_id": recruiter_id,
        "applicant_id": applicant_id,
        "job_id": job_id,
        "chunk_length": len(chunk)
    }
    # Optional: extract years
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', chunk)
    if years:
        metadata["years"] = ",".join(sorted(set(years)))
    
    return metadata