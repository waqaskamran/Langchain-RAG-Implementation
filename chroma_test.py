# chroma_test.py
print("Starting Chroma test...")

from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma

# Initialize local embeddings (no API key needed)
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# Initialize Chroma vectorstore
vectorstore = Chroma(
    collection_name="recruiters",
    embedding_function=embeddings,
    persist_directory="chroma_db"  # this folder will store embeddings
)

collection = vectorstore._collection
print("Chroma collection:", collection)

# Add some sample recruiter data
texts = [
    "Sarah Johnson, recruiter at XYZ Corp, email: sarah.j@xyz.com",
    "David Lee, HR at ABC Ltd, email: david.lee@abcltd.com"
]
vectorstore.add_texts(texts)

# Query the vectorstore
query = "What is Sarah Johnson's email?"
results = vectorstore.similarity_search(query, k=1)

print("Query Result:", results[0].page_content)
