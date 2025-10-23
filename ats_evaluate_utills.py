import re
from sklearn.metrics.pairwise import cosine_similarity


def extract_keywords_from_jd(jd_text):
    """
    Extract skills / certifications from job description.
    You can improve this using regex or predefined skill lists.
    """
    # Example: split by commas, keywords, etc.
    keywords = re.findall(r'\b(Java|Spring Boot|Azure|Microservices|Swagger|CI/CD)\b', jd_text, re.IGNORECASE)
    return set([k.lower() for k in keywords])

def evaluate_resume_hybrid(resume_chunks, jd_chunks):
    # Combine resume text
    resume_text = "\n".join([c.page_content for c in resume_chunks])
    jd_text = "\n".join([c.page_content for c in jd_chunks])

    # 1️⃣ Embedding similarity (can be replaced with actual embedding similarity function)
    embedding_similarity = 41.47  # placeholder, compute via vector similarity if needed

    # 2️⃣ LLM evaluation
    prompt = f"""
    You are an expert recruiter. Compare the resume below with the job description.
    
    RESUME:
    {resume_text}
    
    JOB DESCRIPTION:
    {jd_text}
    
    Evaluate the match score (0-100), list key matched skills, and missing skills.
    Answer in JSON format:
    {{
        "llm_score": <score>,
        "matched_skills": [...],
        "missing_skills": [...]
    }}
    """

    from app import query_ollama
    import json
    
    llm_response = query_ollama(prompt)
    llm_data = json.loads(llm_response)  # ensure LLM returns JSON

    # 3️⃣ Keyword / ATS score
    jd_keywords = extract_keywords_from_jd(jd_text)
    keyword_score, missing_skills_from_keywords = compute_keyword_score(resume_text, jd_keywords)

    # 4️⃣ Final score: hybrid weighting
    final_score = round(
        0.4 * embedding_similarity + 0.3 * llm_data.get("llm_score", 0) + 0.3 * keyword_score
    )

    # 5️⃣ Merge missing skills from LLM + keyword analysis
    missing_skills = list(set(llm_data.get("missing_skills", []) + missing_skills_from_keywords))

    return {
        "embedding_similarity": embedding_similarity,
        "llm_score": llm_data.get("llm_score", 0),
        "keyword_score": keyword_score,
        "final_score": final_score,
        "matched_skills": llm_data.get("matched_skills", []),
        "missing_skills": missing_skills
    }


def compute_embedding_similarity(resume_text, jd_text, embeddings):
    """
    Compute cosine similarity (0-100) between resume and JD embeddings.
    
    Args:
        resume_text (str): Full text of the candidate's resume.
        jd_text (str): Full text of the job description.
        embeddings: LangChain embeddings object (e.g., HuggingFaceEmbeddings)

    Returns:
        float: Similarity score between 0 and 100
    """
    if not resume_text or not jd_text:
        return 0.0

    # Generate embeddings
    resume_emb_list = embeddings.embed_documents([resume_text])
    jd_emb_list = embeddings.embed_documents([jd_text])

    if not resume_emb_list or not jd_emb_list:
        return 0.0

    resume_emb = resume_emb_list[0]
    jd_emb = jd_emb_list[0]

    # Compute cosine similarity
    similarity = cosine_similarity([resume_emb], [jd_emb])[0][0]

    # Scale to 0-100
    similarity_score = round(float(similarity * 100), 2)
    return similarity_score

def compute_keyword_score(resume_text, jd_text):
    """Simple keyword matching without LLM"""
    resume_lower = resume_text.lower()
    jd_lower = jd_text.lower()
    
    # Extract important keywords from JD (simple approach)
    jd_words = set(word for word in jd_lower.split() if len(word) > 4)
    resume_words = set(word for word in resume_lower.split() if len(word) > 4)
    
    if not jd_words:
        return 0
    
    matched = len(jd_words.intersection(resume_words))
    score = (matched / len(jd_words)) * 100
    
    return min(round(score), 100)