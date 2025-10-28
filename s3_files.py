# routes/files_api.py

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import boto3
from botocore.exceptions import ClientError
import os
from datetime import datetime
import uuid
import logging

files_bp = Blueprint('files', __name__, url_prefix='/api/files')

# Configure S3/MinIO client
s3_client = boto3.client(
    's3',
    endpoint_url=os.getenv('MINIO_ENDPOINT', 'http://minio:9001'),  # MinIO endpoint
    aws_access_key_id=os.getenv('MINIO_ACCESS_KEY', 'minioadmin'),
    aws_secret_access_key=os.getenv('MINIO_SECRET_KEY', 'docuadmin123'),
    region_name='us-east-1'
)

BUCKET_NAME = os.getenv('MINIO_BUCKET', 'docusense')
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



@files_bp.route('/test/s3', methods=['GET'])
def test_minio():
    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
            aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "docuadmin"),
            aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "docuadmin123"),
            region_name="us-east-1",
        )
        buckets = s3.list_buckets()
        return jsonify({
            "status": "success",
            "buckets": [b["Name"] for b in buckets.get("Buckets", [])]
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    
    

@files_bp.route('/upload/resume', methods=['POST'])
@jwt_required()
def upload_resume():
    """
    Upload resume file to S3/MinIO
    
    Form Data:
    - file: The resume file (PDF, DOC, DOCX)
    
    Response:
    {
        "success": true,
        "file_url": "https://s3.amazonaws.com/bucket/resumes/uuid-filename.pdf",
        "file_name": "john-doe-resume.pdf",
        "file_size": 245678
    }
    """
    try:
        current_user_id = int(get_jwt_identity())
        
        # Check if file is present
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({
                'error': 'Invalid file type. Only PDF, DOC, DOCX allowed'
            }), 400
        
        # Check file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                'error': f'File too large. Maximum size is {MAX_FILE_SIZE / 1024 / 1024}MB'
            }), 400
        
        # Generate unique filename
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"resumes/{current_user_id}/{uuid.uuid4()}.{file_extension}"
        
        # Upload to S3/MinIO
        s3_client.upload_fileobj(
            file,
            BUCKET_NAME,
            unique_filename,
            ExtraArgs={
                'ContentType': file.content_type,
                'Metadata': {
                    'user_id': str(current_user_id),
                    'original_filename': original_filename,
                    'uploaded_at': datetime.utcnow().isoformat()
                }
            }
        )
        
        # Generate public URL (or presigned URL)
        file_url = f"{os.getenv('MINIO_ENDPOINT', 'http://localhost:9000')}/{BUCKET_NAME}/{unique_filename}"

        logging.info(f"User {current_user_id} uploaded resume: {file_url}")
        
        # Optional: Save to database for tracking
        from models import db, ApplicantProfile
        profile = ApplicantProfile.query.filter_by(user_id=current_user_id).first()
        if profile:
            profile.resume_url = file_url
            profile.resume_uploaded_at = datetime.utcnow()
            db.session.commit()
        
        return jsonify({
            'success': True,
            'file_url': file_url,
            'file_name': original_filename,
            'file_size': file_size,
            'message': 'Resume uploaded successfully'
        }), 200
        
    except ClientError as e:
        return jsonify({
            'error': 'Failed to upload file to storage',
            'details': str(e)
        }), 500
    except Exception as e:
        return jsonify({
            'error': 'Upload failed',
            'details': str(e)
        }), 500


@files_bp.route('/upload/portfolio', methods=['POST'])
@jwt_required()
def upload_portfolio():
    """Similar implementation for portfolio files"""
    # Same logic as resume upload
    pass