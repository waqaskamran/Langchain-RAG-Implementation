CREATE SCHEMA IF NOT EXISTS docusense;

SET search_path TO docusense;

-- ============================================================
--  USERS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(80) NOT NULL,
    last_name VARCHAR(80),
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'applicant',  -- 'applicant', 'recruiter', 'admin'
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);





-- ============================================================
--  INDEXES FOR PERFORMANCE
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
============================================




-- relationship table between users and roles

CREATE TABLE docusense.user_roles (
    user_id INT REFERENCES docusense.users(id) ON DELETE CASCADE,
    role_id INT REFERENCES docusense.roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

SET search_path TO docusense;

-- =====================================================
-- 1. SKILLS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS docusense.skills (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_skills_name ON docusense.skills(name);
CREATE INDEX idx_skills_category ON docusense.skills(category);


-- =====================================================
-- 2. ENHANCED JOBS TABLE
-- =====================================================
-- Drop existing jobs table if you want to recreate with new structure
-- DROP TABLE IF EXISTS docusense.jobs CASCADE;

CREATE TABLE IF NOT EXISTS docusense.jobs (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    
    -- Job Details
    company_name VARCHAR(200),
    department VARCHAR(100),
    employment_type VARCHAR(50), -- full-time, part-time, contract, internship
    experience_level VARCHAR(50), -- entry, mid, senior, lead, executive
    
    -- Location
    location VARCHAR(200),
    is_remote BOOLEAN DEFAULT FALSE,
    remote_type VARCHAR(50), -- fully_remote, hybrid, on_site
    
    -- Compensation
    salary_min INTEGER,
    salary_max INTEGER,
    salary_currency VARCHAR(10) DEFAULT 'USD',
    salary_period VARCHAR(20) DEFAULT 'yearly', -- yearly, monthly, hourly
    
    -- Requirements
    requirements TEXT,
    responsibilities TEXT,
    benefits TEXT,
    education_required VARCHAR(100),
    years_of_experience INTEGER,
    
    -- Application Settings
    application_deadline TIMESTAMP,
    max_applications INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    posted_by INTEGER NOT NULL REFERENCES docusense.users(id) ON DELETE CASCADE,
    views_count INTEGER DEFAULT 0,
    applications_count INTEGER DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    
    CONSTRAINT check_salary_range CHECK (salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max),
    CONSTRAINT check_experience CHECK (years_of_experience IS NULL OR years_of_experience >= 0)
);

-- Indexes for jobs table
CREATE INDEX idx_jobs_title ON docusense.jobs(title);
CREATE INDEX idx_jobs_company ON docusense.jobs(company_name);
CREATE INDEX idx_jobs_location ON docusense.jobs(location);
CREATE INDEX idx_jobs_employment_type ON docusense.jobs(employment_type);
CREATE INDEX idx_jobs_experience_level ON docusense.jobs(experience_level);
CREATE INDEX idx_jobs_is_active ON docusense.jobs(is_active);
CREATE INDEX idx_jobs_posted_by ON docusense.jobs(posted_by);
CREATE INDEX idx_jobs_created_at ON docusense.jobs(created_at DESC);
CREATE INDEX idx_jobs_salary ON docusense.jobs(salary_min, salary_max);
CREATE INDEX idx_jobs_deadline ON docusense.jobs(application_deadline);


-- =====================================================
-- 3. JOB_SKILLS ASSOCIATION TABLE (Many-to-Many)
-- =====================================================
CREATE TABLE IF NOT EXISTS docusense.job_skills (
    job_id INTEGER NOT NULL REFERENCES docusense.jobs(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES docusense.skills(id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, skill_id)
);

CREATE INDEX idx_job_skills_job ON docusense.job_skills(job_id);
CREATE INDEX idx_job_skills_skill ON docusense.job_skills(skill_id);


-- =====================================================
-- 4. APPLICATIONS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS docusense.applications (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES docusense.jobs(id) ON DELETE CASCADE,
    applicant_id INTEGER NOT NULL REFERENCES docusense.users(id) ON DELETE CASCADE,
    
    -- Application Status
    status VARCHAR(50) DEFAULT 'submitted',
    -- Possible values: submitted, under_review, shortlisted, interview_scheduled, 
    -- interviewed, offer_extended, hired, rejected, withdrawn
    
    -- Application Data
    cover_letter TEXT,
    resume_url VARCHAR(500),
    portfolio_url VARCHAR(500),
    linkedin_url VARCHAR(500),
    github_url VARCHAR(500),
    
    -- Questionnaire responses (stored as JSON)
    questionnaire_responses JSONB,
    
    -- AI/LLM Analysis
    ai_score FLOAT CHECK (ai_score IS NULL OR (ai_score >= 0 AND ai_score <= 100)),
    ai_summary TEXT,
    skills_match_score FLOAT CHECK (skills_match_score IS NULL OR (skills_match_score >= 0 AND skills_match_score <= 100)),
    
    -- Interview & Process
    interview_scheduled_at TIMESTAMP,
    interview_notes TEXT,
    interviewer_id INTEGER REFERENCES docusense.users(id) ON DELETE SET NULL,
    
    -- Metadata
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    reviewed_by INTEGER REFERENCES docusense.users(id) ON DELETE SET NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE(job_id, applicant_id), -- One application per job per applicant
    CONSTRAINT check_status CHECK (status IN (
        'submitted', 'under_review', 'shortlisted', 'interview_scheduled',
        'interviewed', 'offer_extended', 'hired', 'rejected', 'withdrawn'
    ))
);

-- Indexes for applications
CREATE INDEX idx_applications_job ON docusense.applications(job_id);
CREATE INDEX idx_applications_applicant ON docusense.applications(applicant_id);
CREATE INDEX idx_applications_status ON docusense.applications(status);
CREATE INDEX idx_applications_submitted ON docusense.applications(submitted_at DESC);
CREATE INDEX idx_applications_ai_score ON docusense.applications(ai_score DESC);
CREATE INDEX idx_applications_reviewed_by ON docusense.applications(reviewed_by);
CREATE INDEX idx_applications_interviewer ON docusense.applications(interviewer_id);


-- =====================================================
-- 5. APPLICATION TIMELINE TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS docusense.application_timeline (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES docusense.applications(id) ON DELETE CASCADE,
    
    event_type VARCHAR(50) NOT NULL,
    -- Possible values: submitted, status_changed, reviewed, interview_scheduled, 
    -- note_added, document_uploaded, etc.
    
    event_data JSONB, -- Additional event details
    notes TEXT,
    
    created_by INTEGER REFERENCES docusense.users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_timeline_application ON docusense.application_timeline(application_id);
CREATE INDEX idx_timeline_created_at ON docusense.application_timeline(created_at DESC);
CREATE INDEX idx_timeline_event_type ON docusense.application_timeline(event_type);


-- =====================================================
-- 6. APPLICANT PROFILES TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS docusense.applicant_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES docusense.users(id) ON DELETE CASCADE,
    
    -- Professional Info
    headline VARCHAR(200),
    bio TEXT,
    current_title VARCHAR(200),
    current_company VARCHAR(200),
    years_of_experience INTEGER CHECK (years_of_experience IS NULL OR years_of_experience >= 0),
    
    -- Contact & Links
    phone VARCHAR(20),
    location VARCHAR(200),
    linkedin_url VARCHAR(500),
    github_url VARCHAR(500),
    portfolio_url VARCHAR(500),
    website_url VARCHAR(500),
    
    -- Job Preferences
    desired_job_titles TEXT[], -- Array of desired job titles
    desired_locations TEXT[], -- Array of desired locations
    willing_to_relocate BOOLEAN DEFAULT FALSE,
    desired_salary_min INTEGER,
    desired_salary_max INTEGER,
    desired_employment_types TEXT[], -- Array: full-time, contract, etc.
    available_from TIMESTAMP,
    
    -- Resume
    resume_url VARCHAR(500),
    resume_text TEXT, -- Extracted text for AI analysis
    resume_uploaded_at TIMESTAMP,
    
    -- Metadata
    profile_completeness INTEGER DEFAULT 0 CHECK (profile_completeness >= 0 AND profile_completeness <= 100),
    is_open_to_opportunities BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_profiles_user ON docusense.applicant_profiles(user_id);
CREATE INDEX idx_profiles_location ON docusense.applicant_profiles(location);
CREATE INDEX idx_profiles_experience ON docusense.applicant_profiles(years_of_experience);
CREATE INDEX idx_profiles_open_to_opportunities ON docusense.applicant_profiles(is_open_to_opportunities);


-- =====================================================
-- 7. WORK EXPERIENCE TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS docusense.work_experiences (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES docusense.applicant_profiles(id) ON DELETE CASCADE,
    
    title VARCHAR(200) NOT NULL,
    company VARCHAR(200) NOT NULL,
    location VARCHAR(200),
    employment_type VARCHAR(50), -- full-time, part-time, contract, internship
    
    start_date DATE NOT NULL,
    end_date DATE,
    is_current BOOLEAN DEFAULT FALSE,
    
    description TEXT,
    achievements TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_experience_dates CHECK (end_date IS NULL OR start_date <= end_date)
);

CREATE INDEX idx_experience_profile ON docusense.work_experiences(profile_id);
CREATE INDEX idx_experience_dates ON docusense.work_experiences(start_date DESC, end_date DESC);
CREATE INDEX idx_experience_company ON docusense.work_experiences(company);


-- =====================================================
-- 8. EDUCATION TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS docusense.educations (
    id SERIAL PRIMARY KEY,
    profile_id INTEGER NOT NULL REFERENCES docusense.applicant_profiles(id) ON DELETE CASCADE,
    
    institution VARCHAR(200) NOT NULL,
    degree VARCHAR(100) NOT NULL,
    field_of_study VARCHAR(200),
    
    start_date DATE,
    end_date DATE,
    is_current BOOLEAN DEFAULT FALSE,
    
    grade VARCHAR(50), -- GPA, percentage, etc.
    description TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT check_education_dates CHECK (end_date IS NULL OR start_date IS NULL OR start_date <= end_date)
);

CREATE INDEX idx_education_profile ON docusense.educations(profile_id);
CREATE INDEX idx_education_dates ON docusense.educations(start_date DESC, end_date DESC);
CREATE INDEX idx_education_institution ON docusense.educations(institution);


-- =====================================================
-- 9. SAVED JOBS TABLE
-- =====================================================
CREATE TABLE IF NOT EXISTS docusense.saved_jobs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES docusense.users(id) ON DELETE CASCADE,
    job_id INTEGER NOT NULL REFERENCES docusense.jobs(id) ON DELETE CASCADE,
    
    notes TEXT,
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(user_id, job_id) -- User can save a job only once
);

CREATE INDEX idx_saved_jobs_user ON docusense.saved_jobs(user_id);
CREATE INDEX idx_saved_jobs_job ON docusense.saved_jobs(job_id);
CREATE INDEX idx_saved_jobs_saved_at ON docusense.saved_jobs(saved_at DESC);


-- =====================================================
-- 10. TRIGGERS FOR UPDATED_AT
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all tables with updated_at
CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON docusense.jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_applications_updated_at BEFORE UPDATE ON docusense.applications
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON docusense.applicant_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_experience_updated_at BEFORE UPDATE ON docusense.work_experiences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_education_updated_at BEFORE UPDATE ON docusense.educations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- =====================================================
-- 11. SEED DATA - SKILLS
-- =====================================================

INSERT INTO docusense.skills (name, category) VALUES
-- Technical Skills - Programming Languages
('Python', 'technical'),
('JavaScript', 'technical'),
('TypeScript', 'technical'),
('Java', 'technical'),
('C++', 'technical'),
('Go', 'technical'),
('Rust', 'technical'),
('Ruby', 'technical'),
('PHP', 'technical'),
('Swift', 'technical'),
('Kotlin', 'technical'),

-- Technical Skills - Frameworks & Libraries
('React', 'technical'),
('Angular', 'technical'),
('Vue.js', 'technical'),
('Node.js', 'technical'),
('Django', 'technical'),
('Flask', 'technical'),
('Spring Boot', 'technical'),
('Express.js', 'technical'),
('.NET', 'technical'),
('FastAPI', 'technical'),

-- Technical Skills - Databases
('PostgreSQL', 'technical'),
('MySQL', 'technical'),
('MongoDB', 'technical'),
('Redis', 'technical'),
('Elasticsearch', 'technical'),
('SQL', 'technical'),
('NoSQL', 'technical'),

-- Technical Skills - DevOps & Cloud
('AWS', 'technical'),
('Azure', 'technical'),
('Google Cloud', 'technical'),
('Docker', 'technical'),
('Kubernetes', 'technical'),
('CI/CD', 'technical'),
('Jenkins', 'technical'),
('Git', 'technical'),
('Linux', 'technical'),
('Terraform', 'technical'),

-- Technical Skills - Data & AI
('Machine Learning', 'technical'),
('Deep Learning', 'technical'),
('Data Analysis', 'technical'),
('SQL', 'technical'),
('TensorFlow', 'technical'),
('PyTorch', 'technical'),
('Pandas', 'technical'),
('NumPy', 'technical'),

-- Soft Skills
('Communication', 'soft'),
('Leadership', 'soft'),
('Problem Solving', 'soft'),
('Teamwork', 'soft'),
('Time Management', 'soft'),
('Critical Thinking', 'soft'),
('Creativity', 'soft'),
('Adaptability', 'soft'),
('Project Management', 'soft'),
('Analytical Skills', 'soft')

ON CONFLICT (name) DO NOTHING;


-- =====================================================
-- 12. VIEWS FOR REPORTING
-- =====================================================

-- View: Active jobs with application stats
CREATE OR REPLACE VIEW docusense.v_active_jobs_stats AS
SELECT 
    j.id,
    j.title,
    j.company_name,
    j.location,
    j.employment_type,
    j.is_remote,
    j.salary_min,
    j.salary_max,
    j.created_at,
    j.views_count,
    j.applications_count,
    COUNT(DISTINCT a.id) as actual_applications,
    COUNT(DISTINCT CASE WHEN a.status = 'submitted' THEN a.id END) as pending_applications,
    COUNT(DISTINCT CASE WHEN a.status = 'shortlisted' THEN a.id END) as shortlisted_applications,
    COUNT(DISTINCT CASE WHEN a.status = 'hired' THEN a.id END) as hired_count
FROM docusense.jobs j
LEFT JOIN docusense.applications a ON j.id = a.job_id
WHERE j.is_active = TRUE
GROUP BY j.id;


-- View: Applicant application history
CREATE OR REPLACE VIEW docusense.v_applicant_applications AS
SELECT 
    a.id as application_id,
    a.applicant_id,
    u.first_name,
    u.last_name,
    u.email,
    j.id as job_id,
    j.title as job_title,
    j.company_name,
    a.status,
    a.ai_score,
    a.skills_match_score,
    a.submitted_at,
    a.reviewed_at
FROM docusense.applications a
JOIN docusense.users u ON a.applicant_id = u.id
JOIN docusense.jobs j ON a.job_id = j.id;
