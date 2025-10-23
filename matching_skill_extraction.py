def extract_and_compare_skills(resume_text: str, jd_text: str):
    """
    Uses LLM to extract skills from JD only, then checks resume.
    Two-step process to prevent hallucination.
    """
    from app import query_ollama
    
    # ✅ STEP 1: Extract skills from JD ONLY
    jd_extraction_prompt = f"""
    Extract ONLY the technical skills and requirements explicitly mentioned in this Job Description.
    
    Return ONLY valid JSON (no extra text):
    {{
        "required_skills": [<list of skills mentioned in JD>]
    }}
    
    Rules:
    - Only extract skills actually written in the JD
    - Do NOT add skills you think are related
    - Do NOT infer or assume skills
    - Be specific (e.g., "Azure" not just "Cloud")
    
    JOB DESCRIPTION:
    {jd_text}
    """
    
    jd_skills_response = query_ollama(jd_extraction_prompt)
    jd_required_skills = jd_skills_response.get("required_skills", [])
    
    if not jd_required_skills:
        return {
            "llm_score": 0,
            "keyword_score": 0,
            "matched_skills": [],
            "missing_skills": []
        }
    
    # ✅ STEP 2: Check which JD skills are in resume
    comparison_prompt = f"""
    You have a list of required skills from a Job Description.
    Check which of these skills are mentioned in the Resume.
    
    Required Skills from JD: {jd_required_skills}
    
    Return ONLY valid JSON:
    {{
        "llm_score": <0-100 overall match quality>,
        "matched_skills": [<skills from the list above that ARE in resume>],
        "missing_skills": [<skills from the list above that are NOT in resume>]
    }}
    
    Rules:
    - ONLY use skills from the required skills list above
    - Do NOT add any new skills
    - A skill can only be in matched OR missing, never both
    - Check for synonyms (e.g., "Postgres" matches "PostgreSQL")
    
    RESUME:
    {resume_text}
    """
    
    comparison_response = query_ollama(comparison_prompt)
    
    matched_skills = comparison_response.get("matched_skills", [])
    missing_skills = comparison_response.get("missing_skills", [])
    llm_score = comparison_response.get("llm_score", 0)
    
    # ✅ STEP 3: Validate - remove duplicates
    matched_lower = {s.lower().strip() for s in matched_skills}
    missing_clean = [s for s in missing_skills if s.lower().strip() not in matched_lower]
    
    # ✅ STEP 4: Calculate keyword score
    total_skills = len(matched_skills) + len(missing_clean)
    keyword_score = round(len(matched_skills) / total_skills * 100) if total_skills > 0 else 0
    
    return {
        "llm_score": llm_score,
        "keyword_score": keyword_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_clean,
    }

def extract_and_compare_skills_with_flag(resume_text: str, jd_text: str, only_llm: bool = False):
    """
    Extracts and compares skills between resume and JD.
    Returns matched_skills, missing_skills, LLM score, and keyword score.
    If only_llm=True, skips keyword/skill extraction for speed.
    """

    from app import query_ollama

    # LLM prompt for structured skill evaluation
    prompt = f"""
    You are an expert resume evaluator.
    Extract skills from the Job Description (JD) and Resume, then compare them.

    Return JSON with:
    {{
        "llm_score": <score 0-100>,
        "matched_skills": [...],
        "missing_skills": [...],
        "keyword_score": <ATS-style score 0-100>
    }}

    JOB DESCRIPTION:
    {jd_text}

    RESUME:
    {resume_text}
    """

    llm_response = query_ollama(prompt)

    # Extract LLM results
    llm_score = llm_response.get("llm_score", 0)
    matched_skills = llm_response.get("matched_skills", [])
    missing_skills_llm = llm_response.get("missing_skills", [])

    if only_llm:
        # Skip ATS/keyword matching for speed
        return {
            "llm_score": llm_score,
            "keyword_score": None,
            "matched_skills": [],
            "missing_skills": [],
        }

    # 🔹 Compute missing skills correctly: JD → Resume
    if matched_skills:
        missing_skills = [s for s in matched_skills + missing_skills_llm if s not in resume_text]
    else:
        missing_skills = missing_skills_llm

    # 🔹 Compute keyword/ATS score: % of JD skills present in resume
    total_skills = len(matched_skills) + len(missing_skills)
    keyword_score = round(len(matched_skills) / total_skills * 100) if total_skills > 0 else 0

    return {
        "llm_score": llm_score,
        "keyword_score": keyword_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
    }
