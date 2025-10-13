from flask import Flask, request, jsonify
from langchain.vectorstores import Chroma
from langchain.embeddings import HuggingFaceEmbeddings
import requests
import json
import re

from langchain.llms import Ollama
from langchain.chains import LLMChain, MapReduceDocumentsChain
from langchain.prompts import PromptTemplate
import redis

from langchain.memory import ConversationBufferMemory
from langchain.memory.chat_message_histories import RedisChatMessageHistory
from langchain.memory import ConversationBufferMemory
from langchain.memory import ConversationBufferMemory
from langchain.schema import Document


redis_url = "redis://localhost:6379"

from datetime import timedelta



OLLAMA_URL = "http://localhost:11434/api/generate"
app = Flask(__name__)

# Initialize embeddings + Chroma
embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(collection_name="resume", embedding_function=embeddings, persist_directory="chroma_db")

def query_ollama(prompt):
    payload = {"model": "llama2:latest", "prompt": prompt}
    resp = requests.post(OLLAMA_URL, json=payload, stream=True)
    output = ""
    for line in resp.iter_lines():
        if line:
            output += line.decode("utf-8")
    return output

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


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "").strip()
    session_id = data.get("session_id", "default")


    if not question:
        return jsonify({"answer": "Please provide a question."})
    
    memory = get_memory(session_id)


    # --- Step 1: Rephrase the user question intelligently ---
    try:
        ollama_llm = Ollama(model="llama2")
        langchainPrompt = PromptTemplate.from_template(
            "Rephrase this question to be clearer and optimized for resume-based search context:\nQuestion: {question}\nRephrased:"
        )
        rewriter = LLMChain(prompt=langchainPrompt, memory=memory,llm=ollama_llm)
        refined_text = rewriter.run(question)
    except Exception as e:
        print(f" Rewriter error: {e}")
        refined_text = question  # fallback if rephrasing fails

    print(f"Original Question: {question}")
    print(f"Refined Question: {refined_text}")

    # --- Step 2: Retrieve top relevant chunks from Chroma ---
    try:
        results = vectorstore.similarity_search(refined_text, k=5)
        print("------ CHROMA RESULTS ------")
        for i, chunk in enumerate(results):
         print(f"--- chunk {i} ---")
         print(chunk.page_content)
    except Exception as e:
        return jsonify({"answer": f"Vector search failed: {e}"})

    if not results:
        return jsonify({"answer": "No relevant content found."})

    # --- Step 3: Build final prompt for Ollama LLM ---
    prompt = "Answer the question based on the following resume content:\n\n"
    for chunk in results:
        prompt += chunk.page_content + "\n"
    prompt += f"\nQuestion: {question}\nAnswer:"

    # --- Step 4: Query Ollama API with streaming ---
    payload = {
        "model": "llama2:latest",
        "prompt": prompt,
        "max_tokens": 300
    }

    final_answer = ""
    try:
        response = requests.post(OLLAMA_URL, json=payload, stream=True)
        for line in response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line.decode("utf-8"))
                    final_answer += chunk.get("response", "")
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        return jsonify({"answer": f"Error contacting Ollama: {e}"})

    if not final_answer.strip():
        final_answer = "No relevant answer generated."

    return jsonify({"answer": final_answer.strip()})




#latest ask    
# 
@app.route("/ask-again", methods=["POST"])
def askAgain():
    data = request.get_json()
    question = data.get("question", "").strip()
    session_id = data.get("session_id", "default")

    if not question:
        return jsonify({"answer": "Please provide a question."})

    # --- Step 0: Load memory --
    memory = get_memory(session_id)

    # --- Step 1: Refine the user question using memory ---
    try:
        ollama_llm = Ollama(model="llama2:latest")
        rephrase_prompt = PromptTemplate.from_template(
            "Rephrase this question to be clearer and optimized for resume search:\nQuestion: {question}\nRephrased:"
        )
        rewriter = LLMChain(prompt=rephrase_prompt, llm=ollama_llm, memory=memory)
        refined_question = rewriter.run(question)
    except Exception as e:
        print(f"Rewriter error: {e}")
        refined_question = question  # fallback

    print(f"Original Question: {question}")
    print(f"Refined Question: {refined_question}")

    # --- Step 2: Retrieve top relevant chunks from Chroma ---
    try:
        results = vectorstore.similarity_search(refined_question, k=5)
        if not results:
            return jsonify({"answer": "No relevant content found in resume."})

        print("------ CHROMA RESULTS ------")
        for i, chunk in enumerate(results):
            print(f"--- chunk {i} ---")
            print(chunk.page_content[:200])  # preview first 200 chars
    except Exception as e:
        return jsonify({"answer": f"Vector search failed: {e}"})

    # --- Step 3: Build final prompt for LLM ---
    prompt_text = "Answer the question based ONLY on the resume content below. " \
                  "Do NOT make assumptions. If info is missing, respond with 'No information found.'\n\n"

    for chunk in results:
        prompt_text += chunk.page_content + "\n"

    prompt_text += f"\nQuestion: {question}\nAnswer:"

    # --- Step 4: Query Ollama API ---
    final_answer = ""
    try:
        payload = {
            "model": "llama2:latest",
            "prompt": prompt_text,
            "max_tokens": 300
        }
        response = requests.post(OLLAMA_URL, json=payload, stream=True)
        for line in response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line.decode("utf-8"))
                    final_answer += chunk.get("response", "")
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        return jsonify({"answer": f"Error contacting Ollama: {e}"})

    if not final_answer.strip():
        final_answer = "No relevant answer generated."

    return jsonify({"answer": final_answer.strip()})

# Redis endpoints for memory management 

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
