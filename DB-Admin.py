from flask import Flask, jsonify, request
import chromadb
import numpy as np
from langchain.vectorstores import Chroma
from flask_cors import CORS



app = Flask(__name__)

CORS(app)

# --- 1️⃣ Connect to your persisted Chroma DB directory ---
client = chromadb.PersistentClient(path="./chroma_db")
#vectorstore = client.get_collection("resume_v2")
vectorstore = Chroma(collection_name="resume_v2", persist_directory="chroma_db")



def make_serializable(obj):
    """Convert numpy arrays and non-JSON types into serializable ones."""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(i) for i in obj]
    return obj

@app.route("/collections", methods=["GET"])
def list_collections():
    collections = client.list_collections()
    return jsonify({"collections": [c.name for c in collections]})


# --- 2️⃣ API: List all collections ---
@app.route("/peek/<collection_name>", methods=["GET"])
def peek_collection(collection_name):
    try:
        collection = client.get_collection(collection_name)
        docs = collection.peek(limit=5)
        return jsonify(make_serializable(docs))
    except Exception as e:
        return jsonify({"error": str(e)}), 400




# --- 4️⃣ API: Query collection with search text ---
@app.route("/query/<collection_name>", methods=["POST"])
def query_collection(collection_name):
    data = request.get_json()
    query_text = data.get("query", "")
    if not query_text:
        return jsonify({"error": "Please provide a query."}), 400

    try:
        collection = client.get_collection(collection_name)
        results = collection.query(query_texts=[query_text], n_results=3)
        return jsonify(make_serializable(results))
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# --- 5️⃣ Optional: Delete a collection ---
@app.route("/delete/<collection_name>", methods=["DELETE"])
def delete_collection(collection_name):
    try:
        client.delete_collection(collection_name)
        return jsonify({"message": f"Collection '{collection_name}' deleted."})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    

@app.route("/delete_job_resumes", methods=["POST"])
def delete_job_resumes():
    data = request.get_json()
    recruiter_id = data.get("recruiter_id")
    job_id = data.get("job_id")

    if not all([recruiter_id, job_id]):
        return jsonify({"error": "recruiter_id and job_id required"}), 400

    # delete from vectorstore
    vectorstore.delete(
        where={
            "$and": [
                {"recruiter_id": recruiter_id},
                {"job_id": job_id}
            ]
        }
    )

    return jsonify({
        "message": f"All resumes for recruiter '{recruiter_id}' and job '{job_id}' have been deleted."
    })

@app.route("/debug/vectorstore", methods=["GET"])
def debug_vectorstore():
    """
    Debug API to inspect documents in vectorstore.
    Optional query params: recruiter_id, job_id
    """
    recruiter_id = request.args.get("recruiter_id")
    job_id = request.args.get("job_id")

    # Build where filter dynamically
    where_filter = {}
    if recruiter_id:
        where_filter["recruiter_id"] = recruiter_id.lower()
    if job_id:
        where_filter["job_id"] = job_id.lower()

    try:
        data = vectorstore._collection.get(
            where=where_filter if where_filter else None,
            include=["metadatas"]
        )

        results = []
        for meta in data.get("metadatas", []):
            results.append({
                "recruiter_id": meta.get("recruiter_id"),
                "job_id": meta.get("job_id"),
                "doc_type": meta.get("doc_type"),
                "file_name": meta.get("file_name"),
            })

        return jsonify({
            "total_docs": len(results),
            "filter_used": where_filter,
            "docs": results
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500



@app.route("/debug/find_or_delete_docs", methods=["POST"])
def find_or_delete_docs():
    """
    List or delete all documents for recruiter_id + job_id (case-insensitive).
    JSON body:
    {
        "recruiter_id": "rama5",
        "job_id": "job5",
        "delete": true   # optional, set true to delete
    }
    """
    data = request.get_json() or {}
    recruiter_id = (data.get("recruiter_id") or "").strip().lower()
    job_id = (data.get("job_id") or "").strip().lower()
    delete_flag = data.get("delete", False)

    if not recruiter_id or not job_id:
        return jsonify({"error": "recruiter_id and job_id are required"}), 400

    # --- ✅ Fetch everything from the Chroma collection ---
    all_docs = vectorstore.get(include=["documents", "metadatas"])

    ids = all_docs.get("ids", [])
    metadatas = all_docs.get("metadatas", [])

    matched = []
    ids_to_delete = []

    # --- ✅ Filter case-insensitive by recruiter_id + job_id ---
    for i, meta in enumerate(metadatas):
        meta_r = (meta.get("recruiter_id") or "").strip().lower()
        meta_j = (meta.get("job_id") or "").strip().lower()
        if meta_r == recruiter_id and meta_j == job_id:
            matched.append({
                "id": ids[i],
                "recruiter_id": meta.get("recruiter_id"),
                "job_id": meta.get("job_id"),
                "doc_type": meta.get("doc_type"),
                "file_name": meta.get("file_name")
            })
            ids_to_delete.append(ids[i])

    # --- 🗑️ Delete if requested ---
    if delete_flag and ids_to_delete:
        try:
            vectorstore.delete(ids=ids_to_delete)
            return jsonify({
                "message": f"Deleted {len(ids_to_delete)} document(s)",
                "deleted_count": len(ids_to_delete)
            }), 200
        except Exception as e:
            return jsonify({"error": f"Delete failed: {str(e)}"}), 500

    # --- 📋 Just list matching docs ---
    return jsonify({
        "recruiter_id": recruiter_id,
        "job_id": job_id,
        "found_count": len(matched),
        "matched": matched
    }), 200

# get metadta for a document id
@app.route("/debug-chroma", methods=["GET"])
def debug_chroma():
    recruiter_id = request.args.get("recruiter_id")
    job_id = request.args.get("job_id")
    doc_type = request.args.get("doc_type")

    if not recruiter_id:
        return jsonify({"error": "recruiter_id is required"}), 400

    # Step 1️⃣ — Fetch by recruiter_id first (Chroma only allows one condition)
    data = vectorstore.get(
        where={"recruiter_id": recruiter_id},
        include=["metadatas", "documents"]
    )

    # Step 2️⃣ — Manually filter in Python
    filtered = []
    for meta, doc in zip(data["metadatas"], data["documents"]):
        if job_id and meta.get("job_id") != job_id:
            continue
        if doc_type and meta.get("doc_type") != doc_type:
            continue
        filtered.append({
            "doc_type": meta.get("doc_type"),
            "job_id": meta.get("job_id"),
            "recruiter_id": meta.get("recruiter_id"),
            "file_name": meta.get("file_name"),
            "chunk_length": len(doc),
        })

    return jsonify({
        "filter_used": {"recruiter_id": recruiter_id, "job_id": job_id, "doc_type": doc_type},
        "found_count": len(filtered),
        "sample_metadata": filtered[:10]  # show up to 10 for readability
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
