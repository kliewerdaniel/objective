#!/usr/bin/env python3
"""Qwen3-TTS Web UI - Text-to-speech with voice cloning support."""

import os
import uuid
import re
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file

app = Flask(__name__)
app.config["OUTPUT_DIR"] = "outputs"
app.config["CUSTOM_VOICES_DIR"] = "custom_voices"

os.makedirs(app.config["OUTPUT_DIR"], exist_ok=True)
os.makedirs(app.config["CUSTOM_VOICES_DIR"], exist_ok=True)

# Qwen3-TTS Base model - supports ICL zero-shot voice cloning via ref_audio
QWEN3_MODEL_ID = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-4bit"

# Target audio duration per chunk in seconds
# At normal speech rate (~150 words/min), 20 seconds ≈ 50 words
# We split on sentence boundaries to keep natural pauses
CHUNK_TARGET_SECONDS = 20
WORDS_PER_SECOND_ESTIMATE = 2.5  # ~150 words per minute
WORDS_PER_CHUNK = int(CHUNK_TARGET_SECONDS * WORDS_PER_SECOND_ESTIMATE)  # ~50 words


def get_model_path():
    """Return the model ID for Qwen3-TTS."""
    return QWEN3_MODEL_ID


def split_text_into_chunks(text, max_words=None):
    """Split text into chunks suitable for ~20 second audio segments.
    
    Splits on sentence boundaries (., !, ?, etc.) to maintain natural pauses.
    Each chunk targets approximately max_words words.
    
    Args:
        text: The input text to split
        max_words: Maximum words per chunk (default: WORDS_PER_CHUNK)
    
    Returns:
        List of text chunks
    """
    if max_words is None:
        max_words = WORDS_PER_CHUNK
    
    # Split on sentence boundaries while keeping the delimiters
    # This regex splits after sentence-ending punctuation followed by space
    sentences = re.split(r'(?<=[.!?;:])\s+', text.strip())
    
    # Filter out empty sentences
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if not sentences:
        return [text] if text.strip() else []
    
    chunks = []
    current_chunk = []
    current_word_count = 0
    
    for sentence in sentences:
        sentence_word_count = len(sentence.split())
        
        # If a single sentence is very long, we need to split it further
        if sentence_word_count > max_words * 1.5:
            # Split long sentences on commas or natural pauses
            sub_parts = re.split(r'(?<=,)\s*', sentence)
            for part in sub_parts:
                part = part.strip()
                if not part:
                    continue
                part_word_count = len(part.split())
                
                if current_word_count + part_word_count > max_words and current_chunk:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = [part]
                    current_word_count = part_word_count
                else:
                    current_chunk.append(part)
                    current_word_count += part_word_count
        else:
            if current_word_count + sentence_word_count > max_words and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_word_count = sentence_word_count
            else:
                current_chunk.append(sentence)
                current_word_count += sentence_word_count
    
    # Add remaining chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks if chunks else [text]


@app.route("/")
def index():
    """Render the main page."""
    # Load any custom voices from disk
    custom_voices = []
    custom_dir = app.config["CUSTOM_VOICES_DIR"]
    if os.path.exists(custom_dir):
        for f in sorted(os.listdir(custom_dir)):
            if f.endswith((".wav", ".mp3", ".flac", ".m4a", ".ogg")):
                custom_voices.append(f)
    return render_template("index.html", custom_voices=custom_voices)


@app.route("/api/voices")
def list_voices():
    """Return list of custom voice samples."""
    custom_dir = app.config["CUSTOM_VOICES_DIR"]
    voices = []
    if os.path.exists(custom_dir):
        for f in sorted(os.listdir(custom_dir)):
            ext = f.rsplit(".", 1)[-1].lower()
            if ext in ("wav", "mp3", "flac", "m4a", "ogg"):
                voices.append({
                    "name": f.rsplit(".", 1)[0],
                    "filename": f,
                    "url": f"/custom_voices/{f}"
                })
    return jsonify({"voices": voices})


@app.route("/api/voices", methods=["POST"])
def upload_voice():
    """Upload a voice sample for voice cloning."""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    name = request.form.get("name", "")
    if not name:
        return jsonify({"error": "Voice name is required"}), 400

    name = re.sub(r"[^a-zA-Z0-9_]", "_", name).strip()
    if not name:
        return jsonify({"error": "Voice name must contain valid characters"}), 400

    audio_file = request.files["audio"]
    if not audio_file or audio_file.filename == "":
        return jsonify({"error": "No audio file selected"}), 400

    ext = audio_file.filename.rsplit(".", 1)[-1].lower() if "." in audio_file.filename else "wav"
    if ext not in ("wav", "mp3", "flac", "m4a", "ogg", "aac"):
        return jsonify({"error": f"Unsupported format: {ext}"}), 400

    custom_dir = app.config["CUSTOM_VOICES_DIR"]
    os.makedirs(custom_dir, exist_ok=True)

    # Remove any existing files with same name
    for existing in os.listdir(custom_dir):
        if existing.startswith(f"{name}."):
            os.remove(os.path.join(custom_dir, existing))

    save_path = os.path.join(custom_dir, f"{name}.{ext}")
    audio_file.save(save_path)

    return jsonify({
        "success": True,
        "name": name,
        "filename": f"{name}.{ext}",
        "url": f"/custom_voices/{name}.{ext}"
    }), 200


@app.route("/api/voices/<voice_name>", methods=["DELETE"])
def delete_voice(voice_name):
    """Delete a custom voice sample."""
    custom_dir = app.config["CUSTOM_VOICES_DIR"]
    deleted = False
    for f in os.listdir(custom_dir):
        if f.startswith(f"{voice_name}."):
            os.remove(os.path.join(custom_dir, f))
            deleted = True
    if not deleted:
        return jsonify({"error": "Voice not found"}), 404
    return jsonify({"success": True})


@app.route("/api/generate", methods=["POST"])
def generate():
    """Generate speech with optional voice cloning via reference audio."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    text = data.get("text", "").strip()
    speed = float(data.get("speed", 1.0))
    voice_file = data.get("voice_file", "")  # Custom voice sample filename

    if not text:
        return jsonify({"error": "Text is required"}), 400

    model_id = get_model_path()

    # Resolve path to reference audio if using custom voice
    ref_audio_path = None
    if voice_file:
        ref_audio_path = os.path.join(app.config["CUSTOM_VOICES_DIR"], voice_file)
        if not os.path.exists(ref_audio_path):
            return jsonify({"error": f"Voice sample not found: {voice_file}"}), 404

    try:
        import numpy as np
        import soundfile as sf
        from mlx_audio.tts.utils import load_model

        # Load model
        model = load_model(model_id)

        # For base model: ICL voice cloning needs ref_audio + ref_text
        # Use whisper to auto-transcribe reference audio
        ref_text = None
        if ref_audio_path:
            try:
                from mlx_audio.stt import load as load_stt
                stt_model = load_stt("mlx-community/whisper-large-v3-turbo-asr-fp16")
                ref_text = stt_model.generate(ref_audio_path).text
                print(f"Reference audio transcribed: {ref_text}")
            except Exception as e:
                print(f"Warning: could not transcribe reference audio: {e}")

        # Generate audio
        all_audio = []
        sample_rate = 24000

        for result in model.generate(
            text=text,
            ref_audio=ref_audio_path,
            ref_text=ref_text,
            speed=speed,
            verbose=False,
        ):
            all_audio.append(np.array(result.audio))
            sample_rate = getattr(result, 'sample_rate', sample_rate)

        if not all_audio:
            return jsonify({"error": "No audio generated"}), 500

        audio = np.concatenate(all_audio) if len(all_audio) > 1 else all_audio[0]

        # Save to unique file
        file_id = str(uuid.uuid4())
        output_path = os.path.join(app.config["OUTPUT_DIR"], f"{file_id}.wav")
        sf.write(output_path, audio, sample_rate)

        return jsonify({
            "success": True,
            "file_id": file_id,
            "duration": len(audio) / sample_rate,
            "sample_rate": sample_rate,
            "voice": voice_file.replace(".", " ") if voice_file else "default",
            "speed": speed,
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/custom_voices/<filename>")
def serve_custom_voice(filename):
    """Serve a custom voice audio sample."""
    filename = os.path.basename(filename)
    audio_path = os.path.join(app.config["CUSTOM_VOICES_DIR"], filename)
    if not os.path.exists(audio_path):
        return jsonify({"error": "File not found"}), 404
    return send_file(audio_path, mimetype="audio/mpeg" if filename.endswith(".mp3") else "audio/wav")


@app.route("/api/audio/<file_id>")
def get_audio(file_id):
    """Serve generated audio."""
    output_path = os.path.join(app.config["OUTPUT_DIR"], f"{file_id}.wav")
    if not os.path.exists(output_path):
        return jsonify({"error": "Audio not found"}), 404
    return send_file(output_path, mimetype="audio/wav")


@app.route("/api/history")
def get_history():
    """List generated audio files."""
    output_dir = app.config["OUTPUT_DIR"]
    files = []
    for f in sorted(os.listdir(output_dir), key=lambda x: os.path.getmtime(os.path.join(output_dir, x)), reverse=True):
        if f.endswith(".wav"):
            file_id = f[:-4]
            filepath = os.path.join(output_dir, f)
            files.append({
                "file_id": file_id,
                "filename": f,
                "created_at": os.path.getmtime(filepath),
                "size_bytes": os.path.getsize(filepath)
            })
    return jsonify({"files": files})


@app.route("/api/generate_long", methods=["POST"])
def generate_long():
    """Generate speech for long text by splitting into chunks.
    
    Splits text into ~20 second audio segments, generates each segment,
    then concatenates them into a single output file.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    text = data.get("text", "").strip()
    speed = float(data.get("speed", 1.0))
    voice_file = data.get("voice_file", "")

    if not text:
        return jsonify({"error": "Text is required"}), 400

    # Split text into chunks
    chunks = split_text_into_chunks(text)
    
    if len(chunks) <= 1:
        # If text is short enough, use the regular generate endpoint logic
        # by redirecting to it
        return generate()

    print(f"Long text detected: splitting into {len(chunks)} chunks")
    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i+1}: {len(chunk.split())} words - {chunk[:50]}...")

    model_id = get_model_path()

    # Resolve path to reference audio if using custom voice
    ref_audio_path = None
    if voice_file:
        ref_audio_path = os.path.join(app.config["CUSTOM_VOICES_DIR"], voice_file)
        if not os.path.exists(ref_audio_path):
            return jsonify({"error": f"Voice sample not found: {voice_file}"}), 404

    try:
        import numpy as np
        import soundfile as sf
        from mlx_audio.tts.utils import load_model

        # Load model once
        model = load_model(model_id)

        # Transcribe reference audio once if needed
        ref_text = None
        if ref_audio_path:
            try:
                from mlx_audio.stt import load as load_stt
                stt_model = load_stt("mlx-community/whisper-large-v3-turbo-asr-fp16")
                ref_text = stt_model.generate(ref_audio_path).text
                print(f"Reference audio transcribed: {ref_text}")
            except Exception as e:
                print(f"Warning: could not transcribe reference audio: {e}")

        # Generate audio for each chunk
        all_audio_segments = []
        sample_rate = 24000
        chunk_durations = []

        for i, chunk_text in enumerate(chunks):
            print(f"Generating chunk {i+1}/{len(chunks)}: {len(chunk_text.split())} words")
            chunk_audio = []

            for result in model.generate(
                text=chunk_text,
                ref_audio=ref_audio_path,
                ref_text=ref_text,
                speed=speed,
                verbose=False,
            ):
                chunk_audio.append(np.array(result.audio))
                sample_rate = getattr(result, 'sample_rate', sample_rate)

            if chunk_audio:
                segment = np.concatenate(chunk_audio) if len(chunk_audio) > 1 else chunk_audio[0]
                all_audio_segments.append(segment)
                chunk_durations.append(len(segment) / sample_rate)
                print(f"  Chunk {i+1} generated: {len(segment) / sample_rate:.2f}s")
            else:
                print(f"  Chunk {i+1} produced no audio")

        if not all_audio_segments:
            return jsonify({"error": "No audio generated"}), 500

        # Concatenate all segments with a tiny silence gap (100ms) between them for natural flow
        silence_samples = int(sample_rate * 0.1)  # 100ms silence
        silence = np.zeros(silence_samples, dtype=np.float32)

        final_audio_parts = []
        for i, segment in enumerate(all_audio_segments):
            final_audio_parts.append(segment)
            # Add silence between segments (but not after the last one)
            if i < len(all_audio_segments) - 1:
                final_audio_parts.append(silence)

        audio = np.concatenate(final_audio_parts)

        # Save to unique file
        file_id = str(uuid.uuid4())
        output_path = os.path.join(app.config["OUTPUT_DIR"], f"{file_id}.wav")
        sf.write(output_path, audio, sample_rate)

        total_duration = len(audio) / sample_rate
        print(f"Final audio: {total_duration:.2f}s from {len(all_audio_segments)} chunks")

        return jsonify({
            "success": True,
            "file_id": file_id,
            "duration": total_duration,
            "sample_rate": sample_rate,
            "voice": voice_file.replace(".", " ") if voice_file else "default",
            "speed": speed,
            "chunks": len(all_audio_segments),
            "chunk_durations": chunk_durations,
        }), 200

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500




@app.route("/api/audio/<file_id>", methods=["DELETE"])
def delete_audio(file_id):
    """Delete generated audio."""
    output_path = os.path.join(app.config["OUTPUT_DIR"], f"{file_id}.wav")
    if not os.path.exists(output_path):
        return jsonify({"error": "Audio not found"}), 404
    os.remove(output_path)
    return jsonify({"success": True})


if __name__ == "__main__":
    print("Starting Qwen3-TTS Web UI...")
    print(f"Model: {QWEN3_MODEL_ID}")
    app.run(host="0.0.0.0", port=7860, debug=False)