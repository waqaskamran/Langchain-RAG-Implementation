from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

from sqlalchemy.dialects.postgresql import JSON, ARRAY

db = SQLAlchemy()





# Association table (many-to-many)
user_roles = db.Table(
    'user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('docusense.users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('docusense.roles.id'), primary_key=True),
    schema='docusense'
)

job_skills = db.Table(
    'job_skills',
    db.Column('job_id', db.Integer, db.ForeignKey('docusense.jobs.id'), primary_key=True),
    db.Column('skill_id', db.Integer, db.ForeignKey('docusense.skills.id'), primary_key=True),
    schema='docusense'
)

class Role(db.Model):
    __tablename__ = 'roles'
    __table_args__ = {'schema': 'docusense'}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"<Role {self.name}>"  
    

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'schema': 'docusense'}

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(80), nullable=False)
    last_name = db.Column(db.String(80))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    roles = db.relationship(
        'Role',
        secondary=user_roles,
        backref=db.backref('users', lazy='dynamic')
    )


    # Relationships
    #jobs_posted = db.relationship('Job', backref='poster', lazy=True)
    #applications = db.relationship('Application', backref='applicant', lazy=True)

    def __repr__(self):
        return f"<User {self.email} ({self.role})>"


class ApplicationHistory(db.Model):
    __tablename__ = 'application_history'
    __table_args__ = {'schema': 'docusense'}

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('docusense.applications.id', ondelete='CASCADE'), nullable=False)
    old_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50))
    changed_by = db.Column(db.Integer, db.ForeignKey('docusense.users.id', ondelete='SET NULL'))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ApplicationHistory {self.old_status} -> {self.new_status}>"
    

class Skill(db.Model):
    __tablename__ = 'skills'
    __table_args__ = {'schema': 'docusense'}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50))  # technical, soft, domain, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Skill {self.name}>"


class Job(db.Model):
    __tablename__ = 'jobs'
    __table_args__ = {'schema': 'docusense'}

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    # Job Details
    company_name = db.Column(db.String(200))
    department = db.Column(db.String(100))
    employment_type = db.Column(db.String(50))  # full-time, part-time, contract, internship
    experience_level = db.Column(db.String(50))  # entry, mid, senior, lead, executive
    
    # Location
    location = db.Column(db.String(200))
    is_remote = db.Column(db.Boolean, default=False)
    remote_type = db.Column(db.String(50))  # fully_remote, hybrid, on_site
    
    # Compensation
    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    salary_currency = db.Column(db.String(10), default='USD')
    salary_period = db.Column(db.String(20), default='yearly')  # yearly, monthly, hourly
    
    # Requirements
    requirements = db.Column(db.Text)
    responsibilities = db.Column(db.Text)
    benefits = db.Column(db.Text)
    education_required = db.Column(db.String(100))
    years_of_experience = db.Column(db.Integer)
    
    # Application Settings
    application_deadline = db.Column(db.DateTime)
    max_applications = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)
    
    # Metadata
    posted_by = db.Column(db.Integer, db.ForeignKey('docusense.users.id'), nullable=False)
    views_count = db.Column(db.Integer, default=0)
    applications_count = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = db.Column(db.DateTime)
    
    # Relationships
    skills = db.relationship('Skill', secondary=job_skills, backref=db.backref('jobs', lazy='dynamic'))
    applications = db.relationship('Application', backref='job', lazy='dynamic', cascade='all, delete-orphan')
    poster = db.relationship('User', backref='jobs_posted', foreign_keys=[posted_by])

    def to_dict(self, include_applications=False):
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'company_name': self.company_name,
            'department': self.department,
            'employment_type': self.employment_type,
            'experience_level': self.experience_level,
            'location': self.location,
            'is_remote': self.is_remote,
            'remote_type': self.remote_type,
            'salary_min': self.salary_min,
            'salary_max': self.salary_max,
            'salary_currency': self.salary_currency,
            'salary_period': self.salary_period,
            'requirements': self.requirements,
            'responsibilities': self.responsibilities,
            'benefits': self.benefits,
            'education_required': self.education_required,
            'years_of_experience': self.years_of_experience,
            'application_deadline': self.application_deadline.isoformat() if self.application_deadline else None,
            'is_active': self.is_active,
            'views_count': self.views_count,
            'applications_count': self.applications_count,
            'skills': [skill.name for skill in self.skills],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'published_at': self.published_at.isoformat() if self.published_at else None,
        }
        
        if include_applications:
            data['applications'] = [app.to_dict() for app in self.applications]
        
        return data


class Application(db.Model):
    __tablename__ = 'applications'
    __table_args__ = {'schema': 'docusense'}

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('docusense.jobs.id'), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey('docusense.users.id'), nullable=False)
    
    # Application Status
    status = db.Column(db.String(50), default='submitted')  
    # submitted, under_review, shortlisted, interview_scheduled, 
    # interviewed, offer_extended, hired, rejected, withdrawn
    
    # Application Data
    cover_letter = db.Column(db.Text)
    resume_url = db.Column(db.String(500))
    portfolio_url = db.Column(db.String(500))
    linkedin_url = db.Column(db.String(500))
    github_url = db.Column(db.String(500))
    
    # Questionnaire responses (JSON format)
    questionnaire_responses = db.Column(JSON)
    
    # AI/LLM Analysis
    ai_score = db.Column(db.Float)  # 0-100 score from LLM analysis
    ai_summary = db.Column(db.Text)  # LLM-generated candidate summary
    skills_match_score = db.Column(db.Float)  # Skills matching percentage
    
    # Interview & Process
    interview_scheduled_at = db.Column(db.DateTime)
    interview_notes = db.Column(db.Text)
    interviewer_id = db.Column(db.Integer, db.ForeignKey('docusense.users.id'))
    
    # Metadata
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('docusense.users.id'))
    
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    applicant = db.relationship('User', foreign_keys=[applicant_id], backref='applications')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by], backref='reviewed_applications')
    interviewer = db.relationship('User', foreign_keys=[interviewer_id], backref='interviews_conducted')
    timeline = db.relationship('ApplicationTimeline', backref='application', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self, include_sensitive=False):
        data = {
            'id': self.id,
            'job_id': self.job_id,
            'job_title': self.job.title if self.job else None,
            'applicant_id': self.applicant_id,
            'applicant_name': f"{self.applicant.first_name} {self.applicant.last_name}" if self.applicant else None,
            'applicant_email': self.applicant.email if self.applicant and include_sensitive else None,
            'status': self.status,
            'resume_url': self.resume_url,
            'portfolio_url': self.portfolio_url,
            'linkedin_url': self.linkedin_url,
            'github_url': self.github_url,
            'ai_score': self.ai_score,
            'skills_match_score': self.skills_match_score,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        
        if include_sensitive:
            data.update({
                'cover_letter': self.cover_letter,
                'questionnaire_responses': self.questionnaire_responses,
                'ai_summary': self.ai_summary,
                'interview_scheduled_at': self.interview_scheduled_at.isoformat() if self.interview_scheduled_at else None,
                'interview_notes': self.interview_notes,
            })
        
        return data


class ApplicationTimeline(db.Model):
    __tablename__ = 'application_timeline'
    __table_args__ = {'schema': 'docusense'}

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('docusense.applications.id'), nullable=False)
    
    event_type = db.Column(db.String(50), nullable=False)  
    # submitted, status_changed, reviewed, interview_scheduled, note_added, etc.
    
    event_data = db.Column(JSON)  # Additional event details
    notes = db.Column(db.Text)
    
    created_by = db.Column(db.Integer, db.ForeignKey('docusense.users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    creator = db.relationship('User', backref='timeline_events')


class ApplicantProfile(db.Model):
    """Extended profile for job applicants"""
    __tablename__ = 'applicant_profiles'
    __table_args__ = {'schema': 'docusense'}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('docusense.users.id'), unique=True, nullable=False)
    
    # Professional Info
    headline = db.Column(db.String(200))  # Professional headline
    bio = db.Column(db.Text)
    current_title = db.Column(db.String(200))
    current_company = db.Column(db.String(200))
    years_of_experience = db.Column(db.Integer)
    
    # Contact & Links
    phone = db.Column(db.String(20))
    location = db.Column(db.String(200))
    linkedin_url = db.Column(db.String(500))
    github_url = db.Column(db.String(500))
    portfolio_url = db.Column(db.String(500))
    website_url = db.Column(db.String(500))
    
    # Job Preferences
    desired_job_titles = db.Column(ARRAY(db.String))
    desired_locations = db.Column(ARRAY(db.String))
    willing_to_relocate = db.Column(db.Boolean, default=False)
    desired_salary_min = db.Column(db.Integer)
    desired_salary_max = db.Column(db.Integer)
    desired_employment_types = db.Column(ARRAY(db.String))  # full-time, contract, etc.
    available_from = db.Column(db.DateTime)
    
    # Resume
    resume_url = db.Column(db.String(500))
    resume_text = db.Column(db.Text)  # Extracted text for AI analysis
    resume_uploaded_at = db.Column(db.DateTime)
    
    # Metadata
    profile_completeness = db.Column(db.Integer, default=0)  # 0-100%
    is_open_to_opportunities = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('applicant_profile', uselist=False))
    experiences = db.relationship('WorkExperience', backref='profile', lazy='dynamic', cascade='all, delete-orphan')
    educations = db.relationship('Education', backref='profile', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'headline': self.headline,
            'bio': self.bio,
            'current_title': self.current_title,
            'current_company': self.current_company,
            'years_of_experience': self.years_of_experience,
            'phone': self.phone,
            'location': self.location,
            'linkedin_url': self.linkedin_url,
            'github_url': self.github_url,
            'portfolio_url': self.portfolio_url,
            'website_url': self.website_url,
            'desired_job_titles': self.desired_job_titles,
            'desired_locations': self.desired_locations,
            'willing_to_relocate': self.willing_to_relocate,
            'desired_salary_min': self.desired_salary_min,
            'desired_salary_max': self.desired_salary_max,
            'desired_employment_types': self.desired_employment_types,
            'available_from': self.available_from.isoformat() if self.available_from else None,
            'resume_url': self.resume_url,
            'profile_completeness': self.profile_completeness,
            'is_open_to_opportunities': self.is_open_to_opportunities,
            'experiences': [exp.to_dict() for exp in self.experiences],
            'educations': [edu.to_dict() for edu in self.educations],
        }


class WorkExperience(db.Model):
    __tablename__ = 'work_experiences'
    __table_args__ = {'schema': 'docusense'}

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('docusense.applicant_profiles.id'), nullable=False)
    
    title = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(200), nullable=False)
    location = db.Column(db.String(200))
    employment_type = db.Column(db.String(50))
    
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    is_current = db.Column(db.Boolean, default=False)
    
    description = db.Column(db.Text)
    achievements = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'company': self.company,
            'location': self.location,
            'employment_type': self.employment_type,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_current': self.is_current,
            'description': self.description,
            'achievements': self.achievements,
        }


class Education(db.Model):
    __tablename__ = 'educations'
    __table_args__ = {'schema': 'docusense'}

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('docusense.applicant_profiles.id'), nullable=False)
    
    institution = db.Column(db.String(200), nullable=False)
    degree = db.Column(db.String(100), nullable=False)
    field_of_study = db.Column(db.String(200))
    
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    is_current = db.Column(db.Boolean, default=False)
    
    grade = db.Column(db.String(50))
    description = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'institution': self.institution,
            'degree': self.degree,
            'field_of_study': self.field_of_study,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'is_current': self.is_current,
            'grade': self.grade,
            'description': self.description,
        }


class SavedJob(db.Model):
    """Jobs saved/bookmarked by applicants"""
    __tablename__ = 'saved_jobs'
    __table_args__ = {'schema': 'docusense'}

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('docusense.users.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('docusense.jobs.id'), nullable=False)
    
    notes = db.Column(db.Text)
    saved_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='saved_jobs')
    job = db.relationship('Job', backref='saved_by_users')