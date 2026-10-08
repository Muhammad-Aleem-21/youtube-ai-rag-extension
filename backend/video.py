import glob
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import traceback
import uuid
from pathlib import Path

import imageio_ffmpeg
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from rag import Snippet, groq_client, store_transcript

video_router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# ---- limits (override in Railway > Variables, no code change needed) ----
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "2048"))          # 2 GB
MAX_DURATION_MIN = int(os.getenv("MAX_DURATION_MIN", "240"))     # 4 hours
MAX_DURATION_SEC = MAX_DURATION_MIN * 60
CHUNK_SEC = 600                 # 10-minute audio parts (~4.8 MB at 64 kbps, far below Groq's 25 MB)
MAX_ACTIVE_JOBS = 3
MAX_STORED_JOBS = 50
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-large-v3")
ALLOWED_EXT = {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".m4a", ".wav"}

LANG_NAMES = {
    "en": "English", "hi": "Hindi", "ur": "Urdu", "ar": "Arabic", "bn": "Bengali",
    "pa": "Punjabi", "ta": "Tamil", "te": "Telugu", "es": "Spanish", "fr": "French",
    "de": "German", "pt": "Portuguese", "ru": "Russian", "tr": "Turkish",
    "id": "Indonesian", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
}
ALLOWED_LANGS = set(LANG_NAMES)

jobs = {}
transcripts = {}                 # job_id -> {"language": str, "segments": [{"start", "text"}]}
_slot = threading.Semaphore(1)   # process one video at a time


def log(msg):
    print(f"[UPLOAD] {msg}", flush=True)


def _lang_str(value, default=None):
    """Always return a plain string (or the default), even if given a tuple/list."""
    if isinstance(value, (tuple, list)):
        value = value[0] if value else None
    value = str(value).strip() if value else ""
    return value or default


def _prune():
    """Keep memory bounded: drop the oldest finished jobs and their transcripts."""
    finished = [k for k, j in jobs.items() if j["status"] in ("done", "error")]
    finished.sort(key=lambda k: jobs[k].get("created", 0))
    for k in finished[:-MAX_STORED_JOBS]:
        jobs.pop(k, None)
        transcripts.pop(k, None)


def _duration(path):
    r = subprocess.run([FFMPEG, "-i", path], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if not m:
        return 0.0
    h, mi, s = m.groups()
    return int(h) * 3600 + int(mi) * 60 + float(s)


def _transcribe_part(path, language=None):
    kwargs = {}
    if language:
        kwargs["language"] = language

    with open(path, "rb") as f:
        resp = groq_client.audio.transcriptions.create(
            file=(os.path.basename(path), f.read()),
            model=WHISPER_MODEL,
            response_format="verbose_json",
            temperature=0,
            **kwargs,
        )

    data = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
    segs = data.get("segments") or []
    if not segs and data.get("text"):
        segs = [{"start": 0, "end": _duration(path), "text": data["text"]}]

    detected = _lang_str(data.get("language"), "english")
    return segs, detected


def process_video(job_id, src, work_dir, forced_lang=None):
    job = jobs[job_id]
    try:
        job.update(status="queued", message="Waiting in queue...")
        with _slot:
            job.update(status="processing", message="Extracting audio...")
            total = _duration(src)
            log(f"{job_id}: duration {total:.0f}s")

            if total <= 0:
                raise ValueError("Could not read this video file.")
            if total > MAX_DURATION_SEC:
                raise ValueError(
                    f"Video is too long (max {MAX_DURATION_MIN} minutes)."
                )

            pattern = os.path.join(work_dir, "part_%03d.mp3")
            proc = subprocess.run(
                [FFMPEG, "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000",
                 "-c:a", "libmp3lame", "-b:a", "64k",
                 "-f", "segment", "-segment_time", str(CHUNK_SEC),
                 "-reset_timestamps", "1", pattern],
                capture_output=True, text=True,
            )
            if proc.returncode != 0:
                log(f"{job_id}: ffmpeg error: {proc.stderr[-500:]}")
                raise ValueError("Could not extract audio from this file.")

            os.remove(src)   # free disk space as early as possible
            parts = sorted(glob.glob(os.path.join(work_dir, "part_*.mp3")))
            if not parts:
                raise ValueError("No audio track found in this file.")

            segments, offset, language = [], 0.0, "english"

            for i, part in enumerate(parts, 1):
                job["message"] = f"Transcribing part {i}/{len(parts)}..."
                log(f"{job_id}: {job['message']}")
                part_dur = _duration(part)

                segs, detected = _transcribe_part(part, forced_lang)
                if i == 1:
                    language = forced_lang or detected
                    log(f"{job_id}: language = {language}")

                for s in segs:
                    text = (s.get("text") or "").strip()
                    if text:
                        start = offset + float(s.get("start", 0))
                        end = offset + float(s.get("end", 0))
                        segments.append(
                            Snippet(text=text, start=start, duration=max(end - start, 0))
                        )
                offset += part_dur
                os.remove(part)

            if not segments:
                raise ValueError("No speech was detected in this file.")

            language = _lang_str(language, "english")

            # Full raw transcript (original language), served on demand to the page
            transcripts[job_id] = {
                "language": LANG_NAMES.get(language, language),
                "segments": [{"start": s.start, "text": s.text} for s in segments],
            }

            job["message"] = "Building search index..."
            log(f"{job_id}: {job['message']}")
            video_id = f"upload_{job_id}"
            count = store_transcript(video_id, segments, language)

            job.update(status="done", message="Ready", video_id=video_id, segments=count)
            log(f"{job_id}: done ({count} segments, language={language})")

    except Exception as error:
        log(f"{job_id}: FAILED: {error!r}")
        traceback.print_exc()   # shows the exact file and line in the terminal
        msg = error.detail if isinstance(error, HTTPException) else str(error)
        job.update(status="error", message=msg or "Processing failed.")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        _prune()


@video_router.get("/upload")
def upload_page():
    return FileResponse(BASE_DIR / "static" / "upload.html")


@video_router.get("/upload-limits")
def upload_limits():
    return {"max_upload_mb": MAX_UPLOAD_MB, "max_duration_min": MAX_DURATION_MIN}


@video_router.post("/upload-video")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form("auto"),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_EXT))}")

    active = sum(1 for j in jobs.values() if j["status"] in ("queued", "processing"))
    if active >= MAX_ACTIVE_JOBS:
        raise HTTPException(429, "Server is busy. Please try again in a few minutes.")

    job_id = uuid.uuid4().hex[:12]
    work_dir = tempfile.mkdtemp(prefix="vid_")
    src = os.path.join(work_dir, "input" + ext)
    size = 0

    try:
        with open(src, "wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_MB * 1024 * 1024:
                    raise HTTPException(413, f"File too large (max {MAX_UPLOAD_MB} MB).")
                out.write(chunk)
    except HTTPException:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
    except OSError:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(507, "The server ran out of disk space for this file. Try a smaller file.")
    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise

    forced_lang = _lang_str(language)
    if forced_lang not in ALLOWED_LANGS:
        forced_lang = None

    log(f"{job_id}: received {file.filename} ({size / 1e6:.1f} MB), language={forced_lang or 'auto'}")
    jobs[job_id] = {
        "status": "queued",
        "message": "Queued...",
        "video_id": None,
        "segments": 0,
        "created": time.time(),
    }
    background_tasks.add_task(process_video, job_id, src, work_dir, forced_lang)

    return {"success": True, "job_id": job_id}


@video_router.get("/upload-status/{job_id}")
def upload_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job. Please upload again.")
    return job


@video_router.get("/upload-transcript/{job_id}")
def upload_transcript(job_id: str):
    data = transcripts.get(job_id)
    if not data:
        raise HTTPException(404, "Transcript not available. Please upload the file again.")
    return data