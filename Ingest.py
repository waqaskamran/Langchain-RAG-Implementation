# ingest.py
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
import pdfplumber

# Initialize embeddings
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Initialize or create Chroma vectorstore
vectorstore = Chroma(
    collection_name="resume",
    embedding_function=embeddings,
    persist_directory="chroma_db"
)

# Path to your resume PDF
pdf_path = "Rana-Java-AI-IL.pdf"

texts = []
metadatas = []

# Read PDF and split by page
with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        if text:
            texts.append(text)
            metadatas.append({"page": i + 1})  # store page number

# Add pages to Chroma
print(f"Page {i+1} content preview:", text[:100])
vectorstore.add_texts(texts=texts, metadatas=metadatas)
print(f"Ingested {len(texts)} pages into Chroma.")

collection = vectorstore._collection

# Number of documents stored
print("Number of documents stored:", len(collection.get()['documents']))


query = "experience at Emaratech"
results = vectorstore.similarity_search(query, k=2)

for r in results:
    print("Matched text:", r.page_content)

