from pathlib import Path
from dotenv import load_dotenv
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from router import router

from rag import fetch_transcript


# --------------------------------------------------
# Environment
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(
    BASE_DIR / ".env",
    override=True
)


# --------------------------------------------------
# FastAPI
# --------------------------------------------------

app = FastAPI(
    title="YouTube AI Assistant API",
    description="RAG backend for the YouTube AI Chrome Extension",
    version="2.0.0"
)


# --------------------------------------------------
# CORS
# --------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=(
        r"^(https://www\.youtube\.com|"
        r"chrome-extension://.*)$"
    ),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --------------------------------------------------
# Request Models
# --------------------------------------------------

class ChatMessage(BaseModel):

    role: str
    content: str


class ChatRequest(BaseModel):

    video_id: str
    question: str
    history: list[ChatMessage] = []


# --------------------------------------------------
# Root
# --------------------------------------------------

@app.get("/")
def root():

    return {
        "message": (
            "YouTube AI Assistant API is running"
        )
    }


# --------------------------------------------------
# Transcript API Endpoint
# --------------------------------------------------

@app.get("/transcript/{video_id}")
def get_transcript(video_id: str):

    video_id = video_id.strip()


    if not video_id:

        raise HTTPException(
            status_code=400,
            detail="Video ID is required."
        )


    transcript = fetch_transcript(
        video_id
    )


    snippets = []


    for item in transcript:

        snippets.append(
            {
                "text": item.text,
                "start": item.start,
                "duration": item.duration
            }
        )


    return {
        "success": True,
        "video_id": video_id,
        "language": transcript.language,
        "language_code": transcript.language_code,
        "is_generated": transcript.is_generated,
        "count": len(snippets),
        "transcript": snippets
    }


# --------------------------------------------------
# Chat Endpoint
# --------------------------------------------------

@app.post("/chat")
def chat(request: ChatRequest):

    try:

        video_id = request.video_id.strip()
        question = request.question.strip()


        # --------------------------------------------
        # Validate Input
        # --------------------------------------------

        if not video_id:

            raise HTTPException(
                status_code=400,
                detail="Video ID is required."
            )


        if not question:

            raise HTTPException(
                status_code=400,
                detail="Question is required."
            )


        print(
            f"\nRAG request:"
            f"\nVideo: {video_id}"
            f"\nQuestion: {question}"
        )


        result = router.invoke({
            "question": question,
            "video_id": video_id,
            "history": request.history,
        })

        answer = result.get("result") or "I couldn't produce an answer."
        chunks = result.get("retrieved_chunks", [])
        flow = result.get("flow", [])

        # ----------------------------------------------
        # Terminal flow summary
        # ----------------------------------------------
        print("\n" + "=" * 50)
        print("[FLOW SUMMARY]")
        print("  " + " → ".join(["START"] + flow + ["END"]))
        print(f"  Tool rounds used: {result.get('tool_rounds', 0)}")
        print("=" * 50 + "\n")

        # ----------------------------------------------
        # Citation / source
        # ----------------------------------------------
        def score_of(c):
            return c.get("score", c.get("keyword_score", 0))

        said_unknown = any(
            phrase in answer.lower()
            for phrase in (
                "don't know based on",
                "do not know based on",
                
            )
        )

        sources = []
#########################################
####################################3
        if chunks and not said_unknown:
            best = max(chunks, key=score_of)
            sources = [{
                "type": "transcript",
                "text": best["text"],
                "start": best["start"],
                "end": best["end"],
                "score": score_of(best),
            }]
        elif result.get("web_sources"):
            sources = [
                {
                    "type": "web",
                    "title": s["title"],
                    "url": s["url"],
                }
                for s in result["web_sources"][:3]      # top 3 links
            ]

        return {
            "success": True,
            "video_id": video_id,
            "question": question,
            "answer": answer,
            "sources": sources,
            "flow": flow,
        }

        # --------------------------------------------
        # Unexpected Route
        # --------------------------------------------

        # raise HTTPException(
        #     status_code=500,
        #     detail=f"Unknown route: {route}"
        # )


    except HTTPException:

        raise


    except Exception as error:

        print(
            "CHAT ERROR:",
            repr(error)
        )


        raise HTTPException(
            status_code=500,
            detail=str(error)
        )