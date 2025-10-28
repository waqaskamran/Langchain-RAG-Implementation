# routes/jobs_api.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Job, Application, Skill, SavedJob, ApplicantProfile, ApplicationTimeline
from datetime import datetime
from sqlalchemy import or_, and_, func
 
from util.decorators import role_required

jobs_bp = Blueprint('jobs', __name__, url_prefix='/api/jobs')


# ==================== PUBLIC JOB LISTINGS ====================

@jobs_bp.route('', methods=['GET'])
def get_jobs():
    """
    Get all active jobs with filtering, search, and pagination
    Query params:
    - search: search in title, description, company
    - location: filter by location
    - remote_type: fully_remote, hybrid, on_site
    - employment_type: full-time, part-time, contract
    - experience_level: entry, mid, senior
    - skills: comma-separated skill names
    - salary_min: minimum salary
    - page: page number (default 1)
    - per_page: items per page (default 20)
    """
    try:
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Build query
        query = Job.query.filter_by(is_active=True)
        
        # Search
        search = request.args.get('search', '').strip()
        if search:
            search_filter = or_(
                Job.title.ilike(f'%{search}%'),
                Job.description.ilike(f'%{search}%'),
                Job.company_name.ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        # Filters
        location = request.args.get('location')
        if location:
            query = query.filter(Job.location.ilike(f'%{location}%'))
        
        remote_type = request.args.get('remote_type')
        if remote_type:
            query = query.filter_by(remote_type=remote_type)
        
        employment_type = request.args.get('employment_type')
        if employment_type:
            query = query.filter_by(employment_type=employment_type)
        
        experience_level = request.args.get('experience_level')
        if experience_level:
            query = query.filter_by(experience_level=experience_level)
        
        # Skills filter
        skills = request.args.get('skills')
        if skills:
            skill_list = [s.strip() for s in skills.split(',')]
            query = query.join(Job.skills).filter(Skill.name.in_(skill_list))
        
        # Salary filter
        salary_min = request.args.get('salary_min', type=int)
        if salary_min:
            query = query.filter(Job.salary_max >= salary_min)
        
        # Sorting
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        if sort_by == 'salary':
            order_column = Job.salary_max
        elif sort_by == 'applications':
            order_column = Job.applications_count
        else:
            order_column = Job.created_at
        
        if sort_order == 'asc':
            query = query.order_by(order_column.asc())
        else:
            query = query.order_by(order_column.desc())
        
        # Paginate
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'jobs': [job.to_dict() for job in pagination.items],
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@jobs_bp.route('/<int:job_id>', methods=['GET'])
def get_job(job_id):
    """Get single job details"""
    try:
        job = Job.query.get_or_404(job_id)
        
        # Increment view count
        job.views_count += 1
        db.session.commit()
        
        return jsonify(job.to_dict()), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== JOB MANAGEMENT (Admin/Recruiter) ====================

@jobs_bp.route('', methods=['POST'])
@jwt_required()
@role_required('admin', 'recruiter')
def create_job():
    """Create a new job posting"""
    try:
        data = request.get_json()
        current_user_id = get_jwt_identity()
        
        # Validate required fields
        required_fields = ['title', 'description', 'employment_type']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create job
        new_job = Job(
            title=data['title'],
            description=data['description'],
            company_name=data.get('company_name'),
            department=data.get('department'),
            employment_type=data['employment_type'],
            experience_level=data.get('experience_level'),
            location=data.get('location'),
            is_remote=data.get('is_remote', False),
            remote_type=data.get('remote_type'),
            salary_min=data.get('salary_min'),
            salary_max=data.get('salary_max'),
            salary_currency=data.get('salary_currency', 'USD'),
            salary_period=data.get('salary_period', 'yearly'),
            requirements=data.get('requirements'),
            responsibilities=data.get('responsibilities'),
            benefits=data.get('benefits'),
            education_required=data.get('education_required'),
            years_of_experience=data.get('years_of_experience'),
            application_deadline=datetime.fromisoformat(data['application_deadline']) if data.get('application_deadline') else None,
            max_applications=data.get('max_applications'),
            posted_by=int(current_user_id),
            published_at=datetime.utcnow() if data.get('publish_now') else None
        )
        
        # Add skills
        skill_names = data.get('skills', [])
        for skill_name in skill_names:
            skill = Skill.query.filter_by(name=skill_name).first()
            if not skill:
                skill = Skill(name=skill_name)
                db.session.add(skill)
            new_job.skills.append(skill)
        
        db.session.add(new_job)
        db.session.commit()
        
        return jsonify({
            'message': 'Job created successfully',
            'job': new_job.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@jobs_bp.route('/<int:job_id>', methods=['PUT'])
@jwt_required()
@role_required('admin', 'recruiter')
def update_job(job_id):
    """Update a job posting"""
    try:
        job = Job.query.get_or_404(job_id)
        data = request.get_json()
        current_user_id = int(get_jwt_identity())
        
        # Check permission
        if job.posted_by != current_user_id:
            # Check if user is admin
            from models import User
            user = User.query.get(current_user_id)
            if not any(role.name == 'admin' for role in user.roles):
                return jsonify({'error': 'Unauthorized'}), 403
        
        # Update fields
        updatable_fields = [
            'title', 'description', 'company_name', 'department', 'employment_type',
            'experience_level', 'location', 'is_remote', 'remote_type',
            'salary_min', 'salary_max', 'salary_currency', 'salary_period',
            'requirements', 'responsibilities', 'benefits', 'education_required',
            'years_of_experience', 'max_applications', 'is_active'
        ]
        
        for field in updatable_fields:
            if field in data:
                setattr(job, field, data[field])
        
        # Update deadline
        if 'application_deadline' in data and data['application_deadline']:
            job.application_deadline = datetime.fromisoformat(data['application_deadline'])
        
        # Update skills
        if 'skills' in data:
            job.skills.clear()
            for skill_name in data['skills']:
                skill = Skill.query.filter_by(name=skill_name).first()
                if not skill:
                    skill = Skill(name=skill_name)
                    db.session.add(skill)
                job.skills.append(skill)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Job updated successfully',
            'job': job.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@jobs_bp.route('/<int:job_id>', methods=['DELETE'])
@jwt_required()
@role_required('admin', 'recruiter')
def delete_job(job_id):
    """Delete/deactivate a job posting"""
    try:
        job = Job.query.get_or_404(job_id)
        current_user_id = int(get_jwt_identity())
        
        # Check permission
        if job.posted_by != current_user_id:
            from models import User
            user = User.query.get(current_user_id)
            if not any(role.name == 'admin' for role in user.roles):
                return jsonify({'error': 'Unauthorized'}), 403
        
        # Soft delete - just deactivate
        job.is_active = False
        db.session.commit()
        
        return jsonify({'message': 'Job deactivated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


# ==================== JOB APPLICATIONS ====================

@jobs_bp.route('/<int:job_id>/apply', methods=['POST'])
@jwt_required()
@role_required('applicant')
def apply_for_job(job_id):

    try:
        # Get the job
        job = Job.query.get_or_404(job_id)
        current_user_id = int(get_jwt_identity())
        data = request.get_json() or {}
        
        # ============ VALIDATIONS ============
        
        # 1. Check if job is still active
        if not job.is_active:
            return jsonify({
                'error': 'This job is no longer accepting applications',
                'error_code': 'JOB_INACTIVE'
            }), 400
        
        # 2. Check application deadline
        if job.application_deadline:
            if datetime.utcnow() > job.application_deadline:
                return jsonify({
                    'error': 'Application deadline has passed',
                    'error_code': 'DEADLINE_PASSED',
                    'deadline': job.application_deadline.isoformat()
                }), 400
        
        # 3. Check maximum applications limit
        if job.max_applications:
            if job.applications_count >= job.max_applications:
                return jsonify({
                    'error': 'Maximum number of applications reached for this position',
                    'error_code': 'MAX_APPLICATIONS_REACHED'
                }), 400
        
        # 4. Check if user already applied
        existing_application = Application.query.filter_by(
            job_id=job_id,
            applicant_id=current_user_id
        ).first()
        
        if existing_application:
            return jsonify({
                'error': 'You have already applied for this job',
                'error_code': 'ALREADY_APPLIED',
                'existing_application': {
                    'id': existing_application.id,
                    'status': existing_application.status,
                    'submitted_at': existing_application.submitted_at.isoformat()
                }
            }), 400
        
        # ============ GET APPLICANT PROFILE DATA ============
        
        # Get applicant profile to auto-fill missing data
        profile = ApplicantProfile.query.filter_by(user_id=current_user_id).first()
        
        # Use provided data or fallback to profile data
        resume_url = data.get('resume_url')
        if not resume_url and profile:
            resume_url = profile.resume_url
        
        portfolio_url = data.get('portfolio_url')
        if not portfolio_url and profile:
            portfolio_url = profile.portfolio_url
        
        linkedin_url = data.get('linkedin_url')
        if not linkedin_url and profile:
            linkedin_url = profile.linkedin_url
        
        github_url = data.get('github_url')
        if not github_url and profile:
            github_url = profile.github_url
        
        # ============ VALIDATE REQUIRED FIELDS ============
        
        # Resume is typically required
        if not resume_url:
            return jsonify({
                'error': 'Resume URL is required to apply',
                'error_code': 'RESUME_REQUIRED'
            }), 400
        
        # ============ CREATE APPLICATION ============
        
        new_application = Application(
            job_id=job_id,
            applicant_id=current_user_id,
            cover_letter=data.get('cover_letter'),
            resume_url=resume_url,
            portfolio_url=portfolio_url,
            linkedin_url=linkedin_url,
            github_url=github_url,
            questionnaire_responses=data.get('questionnaire_responses'),
            status='submitted',
            submitted_at=datetime.utcnow()
        )
        
        db.session.add(new_application)
        
        # ============ UPDATE JOB STATISTICS ============
        
        job.applications_count += 1
        
        # ============ CREATE TIMELINE EVENT ============
        
        timeline_event = ApplicationTimeline(
            application=new_application,
            event_type='submitted',
            notes='Application submitted by applicant',
            created_by=current_user_id,
            event_data={
                'submitted_at': datetime.utcnow().isoformat(),
                'has_cover_letter': bool(data.get('cover_letter')),
                'has_portfolio': bool(portfolio_url),
                'has_questionnaire': bool(data.get('questionnaire_responses'))
            }
        )
        db.session.add(timeline_event)
        
        # ============ COMMIT TO DATABASE ============
        
        db.session.commit()
        
        # ============ PREPARE RESPONSE ============
        
        return jsonify({
            'message': 'Application submitted successfully',
            'application': {
                'id': new_application.id,
                'job_id': job_id,
                'job_title': job.title,
                'company_name': job.company_name,
                'status': new_application.status,
                'submitted_at': new_application.submitted_at.isoformat(),
                'resume_url': new_application.resume_url,
                'portfolio_url': new_application.portfolio_url,
                'linkedin_url': new_application.linkedin_url,
                'github_url': new_application.github_url,
                'has_cover_letter': bool(new_application.cover_letter),
                'has_questionnaire': bool(new_application.questionnaire_responses)
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error in apply_for_job: {str(e)}")
        return jsonify({
            'error': 'Failed to submit application',
            'error_code': 'APPLICATION_FAILED',
            'details': str(e)
        }), 500
    

@jobs_bp.route('/applications/<int:application_id>', methods=['GET'])
@jwt_required()
def get_application(application_id):
    """
    Get application details
    Only accessible by the applicant who created it
    """
    try:
        application = Application.query.get_or_404(application_id)
        current_user_id = int(get_jwt_identity())
        
        # Check if user owns this application
        if application.applicant_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        return jsonify({
            'id': application.id,
            'job_id': application.job_id,
            'job_title': application.job.title,
            'company_name': application.job.company_name,
            'status': application.status,
            'cover_letter': application.cover_letter,
            'resume_url': application.resume_url,
            'portfolio_url': application.portfolio_url,
            'linkedin_url': application.linkedin_url,
            'github_url': application.github_url,
            'questionnaire_responses': application.questionnaire_responses,
            'ai_score': application.ai_score,
            'skills_match_score': application.skills_match_score,
            'submitted_at': application.submitted_at.isoformat(),
            'updated_at': application.updated_at.isoformat() if application.updated_at else None,
            'reviewed_at': application.reviewed_at.isoformat() if application.reviewed_at else None
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500  

    # routes/jobs_api.py

 # ==================== USER APPLICATIONS ====================     

@jobs_bp.route('/my-applications', methods=['GET'])
@jwt_required()
@role_required('applicant')
def get_my_applications():
    """Get all applications by current user"""
    try:
        current_user_id = int(get_jwt_identity())
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status')
        
        query = Application.query.filter_by(applicant_id=current_user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        query = query.order_by(Application.submitted_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        applications = []
        for app in pagination.items:
            app_data = {
                'id': app.id,
                'job_id': app.job_id,
                'job_title': app.job.title if app.job else None,
                'company_name': app.job.company_name if app.job else None,
                'location': app.job.location if app.job else None,
                'employment_type': app.job.employment_type if app.job else None,
                'status': app.status,
                'submitted_at': app.submitted_at.isoformat() if app.submitted_at else None,
                'updated_at': app.updated_at.isoformat() if app.updated_at else None,
                'cover_letter': app.cover_letter,
                'resume_url': app.resume_url,
                'ai_score': app.ai_score,
                'skills_match_score': app.skills_match_score,
            }
            applications.append(app_data)
        
        return jsonify({
            'applications': applications,
            'total': pagination.total,
            'page': page,
            'per_page': per_page,
            'pages': pagination.pages
        }), 200
        
    except Exception as e:
        print(f"Error fetching applications: {str(e)}")
        return jsonify({'error': str(e)}), 500 