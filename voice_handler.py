import os
import io
from flask import Blueprint, request, jsonify, make_response
from flask_cors import CORS
from transformers import pipeline
from transformers import pipeline
from pydub import AudioSegment
import os

# Initialize Whisper once
whisper_asr = pipeline("automatic-speech-recognition", model="openai/whisper-small")


# Create Blueprint once
voice_bp = Blueprint("voice_bp", __name__)

# Apply CORS to blueprint


def run_text_query(query_func, text):
    """Helper to call existing RAG pipeline from main app"""
    return query_func(text)

@voice_bp.route("/voice-query", methods=["POST"])
def voice_query():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    audio_file = request.files["file"]
    if not audio_file or audio_file.filename == "":
        return jsonify({"error": "No audio file provided"}), 400

    filename = audio_file.filename
    file_extension = filename.split('.')[-1] if '.' in filename else 'webm'
    temp_path = f"temp_audio.{file_extension}"
    audio_file.save(temp_path)

    # Convert webm to wav if needed
    if file_extension == "webm":
        audio = AudioSegment.from_file(temp_path, format="webm")
        temp_path_wav = "temp_audio.wav"
        audio.export(temp_path_wav, format="wav")
    else:
        temp_path_wav = temp_path

    # Transcribe
    transcription = whisper_asr(temp_path_wav)["text"]
    from app import build_hybrid_context_and_query

    # Call your RAG pipeline
    rag_response = run_text_query(build_hybrid_context_and_query, transcription)

    # Cleanup
    os.remove(temp_path)
    if temp_path_wav != temp_path:
        os.remove(temp_path_wav)

    return jsonify({"transcription": transcription, "rag_response": rag_response})