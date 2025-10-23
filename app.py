from flask import Flask, request,Response,jsonify
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
import requests
import json
import re

from langchain.llms import Ollama
from langchain.chains import LLMChain, MapReduceDocumentsChain
from langchain.prompts import PromptTemplate
import redis
from flask_cors import CORS

from langchain.memory import ConversationBufferMemory
from langchain.memory.chat_message_histories import RedisChatMessageHistory
from langchain.memory import ConversationBufferMemory
from langchain.memory import ConversationBufferMemory
from langchain.schema import Document
from voice_handler import voice_bp


from datetime import timedelta
from ingest_utils import read_pdf, chunk_text, extract_metadata

import requests
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from flask import Flask, request, jsonify
from matching_skill_extraction import extract_and_compare_skills,extract_and_compare_skills_with_flag

from flask import request, jsonify
import uuid, os
from werkzeug.utils import secure_filename
import uuid
from collections import defaultdict


from ingest_utils import read_pdf, chunk_text, extract_metadata
from ats_evaluate_utills import extract_keywords_from_jd,compute_keyword_score,evaluate_resume_hybrid,compute_embedding_similarity
from flask import request, jsonify


redis_url = "redis://localhost:6379"
OLLAMA_URL = "http://localhost:11434/api/generate"
app = Flask(__name__)
#CORS(app)

CORS(app, resources={r"/*": {"origins": "*"}})
app.config['WTF_CSRF_ENABLED'] = False


# Manual after_request handler for all responses
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    return response

# Initialize embeddings + Chroma

#embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")


vectorstore = Chroma(collection_name="resume_v2", embedding_function=embeddings, persist_directory="chroma_db")

app.register_blueprint(voice_bp)

def query_ollama(prompt, ollama_url="http://localhost:11434/api/generate"):
    """
    Queries Ollama for LLM evaluation and ensures a JSON dict is always returned.
    """

    instruction = (
        "You are a resume evaluator. Analyze the resume against the job description "
        "and return the result strictly as a JSON object with the following fields:\n"
        " - llm_score (integer 0-100)\n"
        " - matched_skills (list of strings)\n"
        " - missing_skills (list of strings)\n\n"
        "Do not include any text outside the JSON."
    )

    full_prompt = f"{instruction}\n\n{prompt}"

    payload = {
        "model": "llama3:8b",
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 300}
    }

    try:
        response = requests.post(ollama_url, json=payload, timeout=40)
        data = response.json()

        # Ollama might return {"response": "..."}
        output = data.get("response", "")

        # Try strict JSON parsing first
        try:
            parsed = json.loads(output)
            return parsed
        except json.JSONDecodeError:
            pass

        # Fallback: extract score using regex if not JSON
        score_match = re.search(r"(\d{1,3})\s*%", output)
        llm_score = int(score_match.group(1)) if score_match else 0

        return {
            "llm_score": llm_score,
            "matched_skills": [],
            "missing_skills": []
        }

    except Exception as e:
        return {
            "llm_score": 0,
            "matched_skills": [],
            "missing_skills": []
        }
    
@app.route("/")
def home():
    return "Flask is running!"


#redis_client = redis.StrictRedis.from_url(redis_url)
REDIS_URL = "redis://localhost:6379/0"
r = redis.from_url(REDIS_URL)

def get_memory(session_id: str):
    
    key = f"message_store:{session_id}"

    # set expiry of 4 hours (14400 seconds)
    r.expire(key, 14400)

    history = RedisChatMessageHistory(
        session_id=session_id,
        url=REDIS_URL
    )
    memory = ConversationBufferMemory(
        chat_memory=history,
        memory_key="chat_history",
        return_messages=True
    )
    return memory


def build_hybrid_context_and_query(question):
    """Helper to perform year-aware vector search, build the strict resume prompt,
    query the Ollama API with streaming, and return the final answer string.
    Returns None if no relevant results were found.
    """
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', question)

    if year_match:
        year = year_match.group(1)
        all_results = vectorstore.similarity_search(question, k=30)
        year_filtered = [r for r in all_results if year in r.page_content]
        results = year_filtered[:5] if year_filtered else all_results[:5]
    else:
        results = vectorstore.similarity_search(question, k=5)

    if not results:
        return None

    # Build context
    context = "\n\n".join([chunk.page_content for chunk in results])

    # Strict prompt to prevent hallucination
    prompt = f"""You are a precise resume analyzer. Follow these rules:

1. Answer ONLY using information from the RESUME CONTEXT below
2. If information exists: provide specific details (companies, dates, projects)
3. If information is NOT in context: say "This information is not mentioned in the resume"
4. DO NOT add any information not explicitly in the context

RESUME CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""

    # Query Ollama
    final_answer = ""
    payload = {
        "model": "llama3:8b",
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_predict": 300
        }
    }

    response = requests.post(OLLAMA_URL, json=payload, stream=True, timeout=30)

    for line in response.iter_lines():
        if line:
            try:
                chunk_data = json.loads(line.decode("utf-8"))
                final_answer += chunk_data.get("response", "")
            except json.JSONDecodeError:
                continue

    return final_answer.strip() or "No answer generated."


# hyrbid ask
@app.route("/ask-hybrid", methods=["POST"])
def ask_hybrid():
    data = request.get_json()
    question = data.get("question", "").strip()
    #response.headers['Referrer-Policy'] = 'no-referrer'

    
    if not question:
        return jsonify({"answer": "Please provide a question."})

    try:
        final_answer = build_hybrid_context_and_query(question)
        if final_answer is None:
            return jsonify({"answer": "No relevant content found."})
    except Exception as e:
        return jsonify({"answer": f"Error: {str(e)}"})
    
    return jsonify({"answer": final_answer})

# ingest Resume and JD and evaluate




@app.route("/ingest_documents", methods=["POST"])
def ingest_documents():
   

    # --- Validate request ---
    if 'resume_file' not in request.files or 'jd_text' not in request.form:
        return jsonify({"error": "Missing resume PDF or job description"}), 400

    resume_pdf = request.files['resume_file']
    jd_text = request.form['jd_text']
    recruiter_id = request.form.get('recruiter_id')
    applicant_id = request.form.get('applicant_id')
    job_id = request.form.get('job_id')

    if not recruiter_id or not applicant_id or not job_id:
        return jsonify({"error": "Missing recruiter_id, applicant_id or job_id"}), 400
    
    existing_docs = vectorstore.similarity_search(
        query="",  # no actual query, just filter
        filter={
            "$and": [
                {"recruiter_id": recruiter_id},
                {"applicant_id": applicant_id},
                {"job_id": job_id},
                {"doc_type": "resume_v2"}
            ]
        },
        k=1
    )

    if existing_docs:
        return jsonify({"error": "Resume for this recruiter, applicant, and job already exists"}), 409

    # --- 1️⃣ Process Resume PDF ---
    resume_text = read_pdf(resume_pdf)
    resume_chunks = chunk_text(resume_text, embeddings)
    resume_metadata = [
        extract_metadata(c, idx, "resume_v2", recruiter_id, applicant_id, job_id)
        for idx, c in enumerate(resume_chunks)
    ]
    vectorstore.add_texts(resume_chunks, resume_metadata)

    # --- 2️⃣ Process Job Description Text ---
    jd_chunks = chunk_text(jd_text, embeddings)
    jd_metadata = [
        extract_metadata(c, idx, "job", recruiter_id, None, job_id)
        for idx, c in enumerate(jd_chunks)
    ]
    vectorstore.add_texts(jd_chunks, jd_metadata)

    return jsonify({
        "message": "Resume and Job Description ingested successfully",
        "resume_chunks": len(resume_chunks),
        "jd_chunks": len(jd_chunks)
    })


# Batch Ingest endpoint
@app.route("/batch_ingest", methods=["POST"])
def batch_ingest():
    """
    Accepts multiple resume PDFs for the same job description.
    Each resume is chunked, embedded, and stored in the vector database.
    """
    recruiter_id = request.form.get("recruiter_id").lower()
    job_id = request.form.get("job_id").lower()
    jd_text = request.form.get("jd_text")
    resume_files = request.files.getlist("resume_files")

    # --- Validation ---
    if not recruiter_id or not job_id or not jd_text:
        return jsonify({"error": "Missing recruiter_id, job_id, or jd_text"}), 400

    if not resume_files or len(resume_files) == 0:
        return jsonify({"error": "No resume files uploaded"}), 400

    processed = []
    failed = []

    try:
        # --- 1️⃣ Process JD once ---
        jd_chunks = chunk_text(jd_text, embeddings)
        jd_metadata = [
            {
                "chunk_index": idx,
                "doc_type": "job",
                "recruiter_id": recruiter_id,
                "file_name": "job_description",
                "job_id": job_id
            }
            for idx, c in enumerate(jd_chunks)
        ]
        vectorstore.add_texts(jd_chunks, jd_metadata)
    except Exception as e:
        return jsonify({"error": f"Failed to process JD: {str(e)}"}), 500

    # --- 2️⃣ Process Each Resume PDF ---
    for resume_pdf in resume_files:
        try:
            resume_text = read_pdf(resume_pdf)

            if not resume_text.strip():
                raise ValueError("Empty PDF")

            resume_chunks = chunk_text(resume_text, embeddings)
            resume_metadata = [
                {
                    "chunk_index": idx,
                    "doc_type": "resume_v2",
                    "recruiter_id": recruiter_id,
                    "file_name": resume_pdf.filename,  # ✅ FIX: Use actual filename
                    "job_id": job_id
                }
                for idx, c in enumerate(resume_chunks)
            ]

            vectorstore.add_texts(resume_chunks, resume_metadata)

            processed.append({
                "file_name": resume_pdf.filename,
                "chunks": len(resume_chunks),
                "status": "success"
            })

        except Exception as e:
            failed.append({
                "file_name": resume_pdf.filename,
                "error": str(e)
            })

    return jsonify({
        "recruiter_id": recruiter_id,
        "job_id": job_id,
        "total_files": len(resume_files),
        "processed_count": len(processed),
        "failed_count": len(failed),
        "processed": processed,
        "failed": failed
    }), 200

#Evaluate resume endpoint


@app.route("/evaluate_resume", methods=["POST"])
def evaluate_resume():
    data = request.get_json()
    recruiter_id = data.get("recruiter_id")
    applicant_id = data.get("applicant_id")
    job_id = data.get("job_id")

    if not all([recruiter_id, applicant_id, job_id]):
        return jsonify({"error": "recruiter_id, applicant_id, and job_id are required"}), 400

    # Fetch resume & JD chunks from vectorstore
    resume_chunks = vectorstore.similarity_search(
        query="",
        filter={
            "$and": [
                {"recruiter_id": recruiter_id},
                {"applicant_id": applicant_id},
                {"job_id": job_id},
                {"doc_type": "resume_v2"},
            ]
        },
        k=10,
    )

    jd_chunks = vectorstore.similarity_search(
        query="",
        filter={
            "$and": [
                {"recruiter_id": recruiter_id},
                {"job_id": job_id},
                {"doc_type": "job"},
            ]
        },
        k=5,
    )

    if not resume_chunks or not jd_chunks:
        return jsonify({"error": "Resume or JD not found"}), 404

    resume_text = "\n".join([c.page_content for c in resume_chunks])
    jd_text = "\n".join([c.page_content for c in jd_chunks])

    #  Extract and compare skills
    skill_results = extract_and_compare_skills(resume_text, jd_text)

    # 🔹 Compute embedding similarity
    embedding_similarity = compute_embedding_similarity(resume_text, jd_text, embeddings)

    # 🔹 Compute final hybrid score (weighted)
    final_score = round(
        0.5 * skill_results["keyword_score"]
        + 0.3 * skill_results["llm_score"]
        + 0.2 * embedding_similarity
    )

    return jsonify({
        "embedding_similarity": embedding_similarity,
        "llm_score": skill_results["llm_score"],
        "keyword_score": skill_results["keyword_score"],
        "final_score": final_score,
        "matched_skills": skill_results["matched_skills"],
        "missing_skills": skill_results["missing_skills"],
    })


#Btach evaluate resumes endpoint

from flask import Flask, request, jsonify
from collections import defaultdict
import uuid
from langchain.schema import Document


@app.route("/evaluate_batch_summary", methods=["POST"])
def evaluate_batch_summary():
    """
    Evaluate resumes in a batch. Returns one result per resume file.
    Mode options: 'fast' (no LLM), 'full' (with LLM), 'auto' (LLM for top 5 only)
    """
    data = request.get_json()
    recruiter_id = data.get("recruiter_id").lower()
    job_id = data.get("job_id").lower()
    mode = data.get("mode", "auto").lower()

    if not all([recruiter_id, job_id]):
        return jsonify({"error": "recruiter_id and job_id required"}), 400

    collection = vectorstore._collection

    # --- Fetch resumes ---
    resume_data = collection.get(
        where={
            "$and": [
                {"recruiter_id": {"$eq": recruiter_id}},
                {"job_id": {"$eq": job_id}},
                {"doc_type": {"$eq": "resume_v2"}}
            ]
        },
        include=["documents", "metadatas"]
    )

    # --- Fetch JD ---
    jd_data = collection.get(
        where={
            "$and": [
                {"recruiter_id": {"$eq": recruiter_id}},
                {"job_id": {"$eq": job_id}},
                {"doc_type": {"$eq": "job"}}
            ]
        },
        include=["documents", "metadatas"]
    )

    if not resume_data["documents"] or not jd_data["documents"]:
        return jsonify({"error": "No resumes or JD found"}), 404

    jd_text = "\n".join(jd_data["documents"])

    # ✅ FIX: Group chunks by file_name
    resumes_by_file = defaultdict(list)
    for doc, meta in zip(resume_data["documents"], resume_data["metadatas"]):
        file_name = meta.get("file_name")
        if not file_name or file_name == "job_description":
            continue  # Skip if no filename or it's JD
        resumes_by_file[file_name].append(doc)

    # --- Evaluate each resume (NOT each chunk) ---
    results = []
    for file_name, chunks in resumes_by_file.items():
        resume_text = "\n".join(chunks)

        # Calculate base scores first (fast)
        keyword_score = compute_keyword_score(resume_text, jd_text)
        embedding_similarity = compute_embedding_similarity(resume_text, jd_text, embeddings)
        
        # Preliminary score without LLM
        prelim_score = round(0.5 * keyword_score + 0.5 * embedding_similarity)
        
        results.append({
            "file_name": file_name,
            "resume_text": resume_text,  # Store for later LLM eval
            "keyword_score": keyword_score,
            "embedding_similarity": round(embedding_similarity, 2),
            "prelim_score": prelim_score,
            "llm_score": 0,
            "matched_skills": [],
            "missing_skills": []
        })
    
    # Sort by preliminary score
    results.sort(key=lambda x: x["prelim_score"], reverse=True)
    
    # --- Apply LLM based on mode ---
    if mode == "full":
        # Run LLM on ALL resumes
        for result in results:
            skill_results = extract_and_compare_skills(result["resume_text"], jd_text)
            result["llm_score"] = skill_results.get("llm_score", 0)
            result["matched_skills"] = skill_results.get("matched_skills", [])
            result["missing_skills"] = skill_results.get("missing_skills", [])
            
    elif mode == "auto":
        # Run LLM only on top 5 candidates (smart optimization)
        for result in results[:5]:
            skill_results = extract_and_compare_skills(result["resume_text"], jd_text)
            result["llm_score"] = skill_results.get("llm_score", 0)
            result["matched_skills"] = skill_results.get("matched_skills", [])
            result["missing_skills"] = skill_results.get("missing_skills", [])
    
    # Calculate final scores with LLM
    for result in results:
        # Adjust weights based on whether LLM was used
        if result["llm_score"] > 0:
            # Full scoring with LLM
            result["final_score"] = round(
                0.4 * result["embedding_similarity"] +  # Semantic understanding
                0.4 * result["llm_score"] +             # AI evaluation
                0.2 * result["keyword_score"]           # Exact matches
            )
        else:
            # Fast mode: prioritize semantic similarity over exact keywords
            result["final_score"] = round(
                0.7 * result["embedding_similarity"] +  # 70% semantic
                0.3 * result["keyword_score"]           # 30% keywords
            )
        
        # Remove resume_text from response (too large)
        result.pop("resume_text", None)
        result.pop("prelim_score", None)
    
    # Re-sort by final score
    results.sort(key=lambda x: x["final_score"], reverse=True)

    return jsonify({
        "recruiter_id": recruiter_id,
        "job_id": job_id,
        "mode": mode,
        "total_evaluated": len(results),
        "results": results
    })
# Redis endpoints for memory management 


@app.route("/get_resume_skill_details", methods=["POST"])
def get_resume_skill_details():
    """
    Returns matched and missing skills for a single resume (by file_name)
    for a given recruiter_id and job_id.
    """
    data = request.get_json()
    recruiter_id = data.get("recruiter_id", "").lower()
    job_id = data.get("job_id", "").lower()
    file_name = data.get("file_name")

    if not all([recruiter_id, job_id, file_name]):
        return jsonify({"error": "recruiter_id, job_id, and file_name required"}), 400

    collection = vectorstore._collection

    # --- Fetch resume chunks for the specific file ---
    resume_data = collection.get(
        where={
            "$and": [
                {"recruiter_id": {"$eq": recruiter_id}},
                {"job_id": {"$eq": job_id}},
                {"doc_type": {"$eq": "resume_v2"}},
                {"file_name": {"$eq": file_name}}
            ]
        },
        include=["documents", "metadatas"]
    )

    # --- Fetch JD chunks ---
    jd_data = collection.get(
        where={
            "$and": [
                {"recruiter_id": {"$eq": recruiter_id}},
                {"job_id": {"$eq": job_id}},
                {"doc_type": {"$eq": "job"}}
            ]
        },
        include=["documents", "metadatas"]
    )

    if not resume_data["documents"]:
        return jsonify({"error": f"No resume found for file: {file_name}"}), 404

    if not jd_data["documents"]:
        return jsonify({"error": f"No JD found for job: {job_id}"}), 404

    # --- Combine chunks into full texts ---
    resume_text = "\n".join(resume_data["documents"])
    jd_text = "\n".join(jd_data["documents"])

    # --- Extract skills comparison ---
    try:
        skill_results = extract_and_compare_skills(resume_text, jd_text)
    except Exception as e:
        print(f"Error in extract_and_compare_skills for {file_name}: {e}")
        return jsonify({"error": str(e)}), 500

    # --- Build response ---
    return jsonify({
        "file_name": file_name,
        "llm_score": skill_results.get("llm_score", 0),
        "matched_skills": skill_results.get("matched_skills", []),
        "missing_skills": skill_results.get("missing_skills", [])
    })



#get Skills from JD and compare with resume
@app.route("/redis/memory/sessions", methods=["GET"])
def get_all_sessions():
    keys = [k.decode("utf-8") for k in r.keys("message_store:*")]
    return jsonify({"sessions": keys})


@app.route("/redis/memory/<session_id>", methods=["GET"])
def get_session_memory(session_id):
    key = f"message_store:{session_id}"
    if not r.exists(key):
        return jsonify({"error": "Session not found"}), 404

    data = r.lrange(key, 0, -1)
    messages = []
    for d in data:
        try:
            msg = json.loads(d.decode("utf-8"))
            messages.append(msg)
        except Exception:
            messages.append({"raw": d.decode("utf-8")})

    return jsonify({
        "session_id": session_id,
        "message_count": len(messages),
        "messages": messages
    })

@app.route("/redis/memory/flush", methods=["DELETE"])
def flush_all_memory():
    r.flushdb()
    return jsonify({"message": "All Redis memory cleared"})



if __name__ == "__main__":
    app.run(debug=True, port=5000)
