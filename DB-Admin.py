from flask import Flask, jsonify, request
import chromadb
import numpy as np

app = Flask(__name__)

# --- 1️⃣ Connect to your persisted Chroma DB directory ---
client = chromadb.PersistentClient(path="./chroma_db")


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
