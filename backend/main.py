# from pathlib import Path
# from dotenv import load_dotenv
# import os

# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel

# from router import router

# from rag import fetch_transcript


# # --------------------------------------------------
# # Environment
# # --------------------------------------------------

# BASE_DIR = Path(__file__).resolve().parent

# load_dotenv(
#     BASE_DIR / ".env",
#     override=True
# )


# # --------------------------------------------------
# # FastAPI
# # --------------------------------------------------

# app = FastAPI(
#     title="YouTube AI Assistant API",
#     description="RAG backend for the YouTube AI Chrome Extension",
#     version="2.0.0"
# )


# # --------------------------------------------------
# # CORS
# # --------------------------------------------------

# app.add_middleware(
#     CORSMiddleware,
#     allow_origin_regex=(
#         r"^(https://www\.youtube\.com|"
#         r"chrome-extension://.*)$"
#     ),
#     allow_credentials=False,
#     allow_methods=["GET", "POST"],
#     allow_headers=["*"],
# )


# # --------------------------------------------------
# # Request Models
# # --------------------------------------------------

# class ChatMessage(BaseModel):

#     role: str
#     content: str


# class ChatRequest(BaseModel):

#     video_id: str
#     question: str
#     history: list[ChatMessage] = []


# # --------------------------------------------------
# # Root
# # --------------------------------------------------

# @app.get("/")
# def root():

#     return {
#         "message": (
#             "YouTube AI Assistant API is running"
#         )
#     }


# # --------------------------------------------------
# # Transcript API Endpoint
# # --------------------------------------------------

# @app.get("/transcript/{video_id}")
# def get_transcript(video_id: str):

#     video_id = video_id.strip()


#     if not video_id:

#         raise HTTPException(
#             status_code=400,
#             detail="Video ID is required."
#         )


#     transcript = fetch_transcript(
#         video_id
#     )


#     snippets = []


#     for item in transcript:

#         snippets.append(
#             {
#                 "text": item.text,
#                 "start": item.start,
#                 "duration": item.duration
#             }
#         )


#     return {
#         "success": True,
#         "video_id": video_id,
#         "language": transcript.language,
#         "language_code": transcript.language_code,
#         "is_generated": transcript.is_generated,
#         "count": len(snippets),
#         "transcript": snippets
#     }


# # --------------------------------------------------
# # Chat Endpoint
# # --------------------------------------------------

# @app.post("/chat")
# def chat(request: ChatRequest):

#     try:

#         video_id = request.video_id.strip()
#         question = request.question.strip()


#         # --------------------------------------------
#         # Validate Input
#         # --------------------------------------------

#         if not video_id:

#             raise HTTPException(
#                 status_code=400,
#                 detail="Video ID is required."
#             )


#         if not question:

#             raise HTTPException(
#                 status_code=400,
#                 detail="Question is required."
#             )


#         print(
#             f"\nRAG request:"
#             f"\nVideo: {video_id}"
#             f"\nQuestion: {question}"
#         )


#         result = router.invoke({
#             "question": question,
#             "video_id": video_id,
#             "history": request.history,
#         })

#         answer = result.get("result") or "I couldn't produce an answer."
#         chunks = result.get("retrieved_chunks", [])
#         flow = result.get("flow", [])

#         # ----------------------------------------------
#         # Terminal flow summary
#         # ----------------------------------------------
#         print("\n" + "=" * 50)
#         print("[FLOW SUMMARY]")
#         print("  " + " → ".join(["START"] + flow + ["END"]))
#         print(f"  Tool rounds used: {result.get('tool_rounds', 0)}")
#         print("=" * 50 + "\n")

#         # ----------------------------------------------
#         # Citation / source
#         # ----------------------------------------------
#         def score_of(c):
#             return c.get("score", c.get("keyword_score", 0))

#         said_unknown = any(
#             phrase in answer.lower()
#             for phrase in (
#                 "don't know based on",
#                 "do not know based on",
                
#             )
#         )

#         sources = []
# #########################################
# ####################################3
#         if chunks and not said_unknown:
#             best = max(chunks, key=score_of)
#             sources = [{
#                 "type": "transcript",
#                 "text": best["text"],
#                 "start": best["start"],
#                 "end": best["end"],
#                 "score": score_of(best),
#             }]
#         elif result.get("web_sources"):
#             sources = [
#                 {
#                     "type": "web",
#                     "title": s["title"],
#                     "url": s["url"],
#                 }
#                 for s in result["web_sources"][:3]      # top 3 links
#             ]

#         return {
#             "success": True,
#             "video_id": video_id,
#             "question": question,
#             "answer": answer,
#             "sources": sources,
#             "flow": flow,
#         }

#         # --------------------------------------------
#         # Unexpected Route
#         # --------------------------------------------

#         # raise HTTPException(
#         #     status_code=500,
#         #     detail=f"Unknown route: {route}"
#         # )


#     except HTTPException:

#         raise


#     except Exception as error:

#         print(
#             "CHAT ERROR:",
#             repr(error)
#         )


#         raise HTTPException(
#             status_code=500,
#             detail=str(error)
#         )


########################
import logging
import os
import re
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rag import get_rag_status, has_rag_data, store_transcript
from router import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("youtube-ai")

app = FastAPI(title="YouTube AI RAG Backend")

# --------------------------------------------------
# CORS (Chrome extensions only)
# --------------------------------------------------
# Optional: set ALLOWED_EXTENSION_ID on Railway to allow exactly one extension.
# Otherwise any well-formed chrome-extension:// origin is allowed.

_extension_id = os.getenv("ALLOWED_EXTENSION_ID", "").strip()

if _extension_id:
    _origin_regex = rf"^chrome-extension://{re.escape(_extension_id)}$"
else:
    _origin_regex = r"^chrome-extension://[a-p]{32}$"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=_origin_regex,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Client-Id"],
)

# --------------------------------------------------
# Models
# --------------------------------------------------

VIDEO_ID_PATTERN = r"^[A-Za-z0-9_-]{11}$"
CLIENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class TranscriptSegment(BaseModel):
    text: str = Field(max_length=5000)
    start: float = Field(ge=0)
    duration: float = Field(default=0.0, ge=0)


class TranscriptUpload(BaseModel):
    video_id: str = Field(pattern=VIDEO_ID_PATTERN)
    transcript: List[TranscriptSegment] = Field(min_length=1, max_length=60000)
    language: Optional[str] = Field(default=None, max_length=100)
    language_code: Optional[str] = Field(default=None, max_length=20)
    is_generated: Optional[bool] = None


class HistoryItem(BaseModel):
    role: str
    content: str = Field(max_length=20000)


class ChatRequest(BaseModel):
    video_id: str = Field(pattern=VIDEO_ID_PATTERN)
    question: str = Field(min_length=1, max_length=4000)
    history: List[HistoryItem] = Field(default_factory=list, max_length=200)


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def api_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )


def make_cache_key(client_id: Optional[str], video_id: str) -> str:
    """
    Transcripts are cached per extension install, so nobody can overwrite
    another user's transcript for the same video ID.
    The router receives this key as its "video_id".
    """
    if not client_id or not CLIENT_ID_PATTERN.match(client_id):
        raise api_error(400, "MISSING_CLIENT_ID", "Missing or invalid X-Client-Id header.")
    return f"{client_id}:{video_id}"


def build_sources(result: dict) -> list:
    sources = []
    seen_starts = set()

    for chunk in result.get("retrieved_chunks") or []:
        start = chunk.get("start")
        if start is None or start in seen_starts:
            continue
        seen_starts.add(start)
        sources.append({
            "type": "transcript",
            "start": float(start),
            "end": chunk.get("end"),
            "text": (chunk.get("text") or "")[:200],
            "score": chunk.get("score", chunk.get("keyword_score")),
        })

    sources.sort(key=lambda s: s["start"])

    for web in result.get("web_sources") or []:
        if web.get("url"):
            sources.append({
                "type": "web",
                "title": web.get("title", ""),
                "url": web["url"],
            })

    return sources


# --------------------------------------------------
# Routes
# --------------------------------------------------

@app.get("/")
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/transcript/{video_id}/status")
def transcript_status(
    video_id: str,
    x_client_id: Optional[str] = Header(default=None),
):
    if not re.match(VIDEO_ID_PATTERN, video_id):
        raise api_error(400, "INVALID_VIDEO_ID", "Invalid video ID.")

    key = make_cache_key(x_client_id, video_id)
    status = get_rag_status(key)

    if not status:
        return {"video_id": video_id, "ready": False}

    return {
        "video_id": video_id,
        "ready": True,
        "count": status["segments"],
        "chunks": status["chunks"],
        "language": status["language"],
        "language_code": status["language_code"],
        "is_generated": status["is_generated"],
    }


@app.post("/transcript")
def upload_transcript(
    request: TranscriptUpload,
    x_client_id: Optional[str] = Header(default=None),
):
    key = make_cache_key(x_client_id, request.video_id)

    try:
        info = store_transcript(
            key,
            [segment.model_dump() for segment in request.transcript],
            request.language,
            request.language_code,
            request.is_generated,
        )
    except ValueError as error:
        logger.warning("Rejected transcript for %s: %s", request.video_id, error)
        raise api_error(422, "NO_USABLE_TRANSCRIPT", "No usable transcript is available for this video.")
    except Exception:
        logger.exception("Failed to build RAG data for %s", request.video_id)
        raise api_error(500, "TRANSCRIPT_PROCESSING_FAILED", "The server could not process the transcript.")

    return {
        "video_id": request.video_id,
        "count": info["segments"],
        "chunks": info["chunks"],
        "language": info["language"],
        "language_code": info["language_code"],
        "is_generated": info["is_generated"],
        "cached": info["cached"],
    }


@app.post("/chat")
def chat(
    request: ChatRequest,
    x_client_id: Optional[str] = Header(default=None),
):
    key = make_cache_key(x_client_id, request.video_id)

    if not has_rag_data(key):
        raise api_error(
            409,
            "TRANSCRIPT_NOT_LOADED",
            "The transcript for this video is not loaded on the server.",
        )

    try:
        result = router.invoke({
            "question": request.question,
            "video_id": key,  # cache key; the tools only use it for get_rag_data()
            "history": request.history[-20:],
        })
    except Exception:
        logger.exception("Chat failed for video %s", request.video_id)
        raise api_error(500, "CHAT_FAILED", "Failed to generate an answer. Please try again.")

    answer = (result.get("result") or "").strip()
    if not answer:
        answer = "Sorry, I couldn't generate an answer for that."

    return {
        "video_id": request.video_id,
        "answer": answer,
        "sources": build_sources(result),
    }