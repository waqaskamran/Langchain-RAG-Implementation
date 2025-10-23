# ingest.py
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_experimental.text_splitter import SemanticChunker
import pdfplumber
import re

# Initialize embeddings
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Initialize Chroma vectorstore
vectorstore = Chroma(
    collection_name="resume",  # use "resume" or "resume_v2" as needed
    embedding_function=embeddings,
    persist_directory="chroma_db"
)

# Path to your resume PDF
pdf_path = "Rana-Java-AI-IL.pdf"

# Read entire PDF text
full_text = ""
with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            full_text += text + "\n"

# Use SemanticChunker
text_splitter = SemanticChunker(
    embeddings=embeddings,
    breakpoint_threshold_type="percentile",
    breakpoint_threshold_amount=90
)

# Split the text into semantically coherent chunks
print("Splitting text semantically...")
chunks = text_splitter.split_text(full_text)

# Dynamic metadata extraction
def extract_metadata(chunk, chunk_id):
    metadata = {
        "chunk_id": chunk_id,
        "chunk_length": len(chunk)
    }
    
    # Extract years - convert list to comma-separated string
    years = re.findall(r'\b(19\d{2}|20\d{2})\b', chunk)
    if years:
        metadata["years"] = ",".join(sorted(set(years)))
    
    # Detect section
    chunk_lower = chunk.lower()
    if "experience" in chunk_lower or "responsibilities" in chunk_lower:
        metadata["section"] = "experience"
    elif "education" in chunk_lower or "certification" in chunk_lower:
        metadata["section"] = "education"
    elif "technical" in chunk_lower or "expertise" in chunk_lower:
        metadata["section"] = "skills"
    elif "summary" in chunk_lower:
        metadata["section"] = "summary"
    else:
        metadata["section"] = "general"
    
    return metadata

# Create metadata for each chunk
metadatas = [extract_metadata(chunks[i], i) for i in range(len(chunks))]

# Clear existing data
try:
    vectorstore._collection.delete(where={})
except:
    pass

# Add chunks to Chroma
vectorstore.add_texts(texts=chunks, metadatas=metadatas)

print(f"✓ Ingested {len(chunks)} semantic chunks into Chroma")