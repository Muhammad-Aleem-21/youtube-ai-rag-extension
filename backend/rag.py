
from pathlib import Path
from dotenv import load_dotenv
import os

from fastapi import HTTPException
from groq import Groq

from sentence_transformers import SentenceTransformer
import faiss

from dataclasses import dataclass

@dataclass
class Snippet:
    text: str
    start: float
    duration: float

# --------------------------------------------------
# Environment
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(
    BASE_DIR / ".env",
    override=True
)


# --------------------------------------------------
# Groq
# --------------------------------------------------

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "Groq key is missing from .env"
    )

groq_client = Groq(
    api_key=GROQ_API_KEY
)


# --------------------------------------------------
# Embedding Model
# --------------------------------------------------

print("Loading embedding model...")

embedding_model = SentenceTransformer(
    "sentence-transformers/all-MiniLM-L6-v2"
)

print("Embedding model loaded.")


# --------------------------------------------------
# RAG Cache
# --------------------------------------------------

rag_cache = {}


# --------------------------------------------------
# Translate Transcript to English (Groq fallback)
# --------------------------------------------------

def _translate_text(text: str) -> str:

    prompt = f"""
Translate the following transcript into natural English.

Rules:
- Translate only.
- Do not summarize.
- Do not add information.
- Preserve the original meaning.
- Return only the English translation.

Transcript:
{text}
"""

    response = groq_client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content.strip()


def translate_transcript_to_english(transcript):

    translated = []

    batch = []
    batch_start = None
    batch_duration = 0
    max_chars = 5000

    def flush():
        nonlocal batch, batch_start, batch_duration
        if not batch:
            return
        translated.append(
            Snippet(
                text=_translate_text(" ".join(batch)),
                start=batch_start,
                duration=batch_duration
            )
        )
        batch = []
        batch_start = None
        batch_duration = 0

    for item in transcript:

        if batch_start is None:
            batch_start = item.start

        batch.append(item.text)
        batch_duration += item.duration

        if len(" ".join(batch)) >= max_chars:
            flush()

    flush()

    return translated

# --------------------------------------------------
# Create Transcript Chunks
# --------------------------------------------------

def create_chunks(transcript):

    chunks = []

    current_text = []
    current_start = None
    current_end = None

    max_chars = 1000


    for item in transcript:

        text = item.text.strip()

        if not text:
            continue


        if current_start is None:

            current_start = item.start


        current_text.append(text)

        current_end = (
            item.start +
            item.duration
        )

        combined = " ".join(
            current_text
        )


        if len(combined) >= max_chars:

            chunks.append(
                {
                    "text": combined,
                    "start": current_start,
                    "end": current_end
                }
            )

            current_text = []
            current_start = None
            current_end = None


    # --------------------------------------------
    # Add Remaining Text
    # --------------------------------------------

    if current_text:

        chunks.append(
            {
                "text": " ".join(current_text),
                "start": current_start,
                "end": current_end
            }
        )


    return chunks


# --------------------------------------------------
# Create FAISS Vector Store
# --------------------------------------------------

def create_vector_store(chunks):

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    embeddings = embedding_model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(
        dimension
    )

    index.add(
        embeddings.astype("float32")
    )

    return index


# --------------------------------------------------
# Retrieve Relevant Chunks
# --------------------------------------------------

def retrieve_chunks(
    question,
    chunks,
    index,
    top_k=4,
    similarity_threshold=0.35
 ):

    question_embedding = (
        embedding_model.encode(
            [question],
            convert_to_numpy=True,
            normalize_embeddings=True
        )
    )


    scores, indices = index.search(
        question_embedding.astype(
            "float32"
        ),
        min(
            top_k,
            len(chunks)
        )
    )


    results = []


    for score, idx in zip(
        scores[0],
        indices[0]
    ):

        if idx == -1:
            continue


        print(
            f"Retrieved chunk score: "
            f"{float(score):.4f} "
            f"| Threshold: "
            f"{similarity_threshold}"
        )


        if (
            float(score) < similarity_threshold
            and len(chunks) > 1
        ):
            continue


        chunk = chunks[idx].copy()

        chunk["score"] = float(
            score
        )

        results.append(
            chunk
        )


    return results

####
def keyword_retrieve_chunks(
    question,
    chunks,
    top_k=4
):
    """
    Second retriever using keyword overlap.
    Useful when semantic similarity does not find
    an obvious transcript match.
    """

    import re

    question_words = set(
        re.findall(
            r"\b[a-zA-Z0-9]{3,}\b",
            question.lower()
        )
    )

    scored_chunks = []

    for chunk in chunks:

        chunk_words = set(
            re.findall(
                r"\b[a-zA-Z0-9]{3,}\b",
                chunk["text"].lower()
            )
        )

        overlap = question_words.intersection(
            chunk_words
        )

        if not overlap:
            continue

        score = len(overlap) / max(
            len(question_words),
            1
        )

        result = chunk.copy()

        result["keyword_score"] = score
        result["matched_keywords"] = list(overlap)

        scored_chunks.append(result)

    scored_chunks.sort(
        key=lambda x: x["keyword_score"],
        reverse=True
    )

    return scored_chunks[:top_k]
# --------------------------------------------------
# Generate RAG Answer
# --------------------------------------------------

def generate_answer(
    question,
    retrieved_chunks,
    history
):

    context_parts = []


    for chunk in retrieved_chunks:

        minutes = int(
            chunk["start"] // 60
        )

        seconds = int(
            chunk["start"] % 60
        )

        timestamp = (
            f"{minutes}:{seconds:02d}"
        )


        context_parts.append(
            f"[Timestamp: {timestamp}]\n"
            f"{chunk['text']}"
        )


    context = "\n\n".join(
        context_parts
    )


    history_text = ""


    if history:

        history_parts = []


        for message in history[-6:]:

            history_parts.append(
                f"{message.role}: "
                f"{message.content}"
            )


        history_text = "\n".join(
            history_parts
        )


    prompt = f"""
You are a YouTube video assistant.

Answer the user's question using ONLY the transcript context provided below.

You may use the conversation history to understand references such as:
"it", "that", "this", "he", "she", or "the previous point".

Do NOT use outside knowledge.

If the transcript does not contain enough information to answer,
say that you don't know based on the video transcript.

Do NOT include timestamps, source references, citations,
or phrases such as "Referenced from timestamps" in your answer.
The application will display the source separately.

TRANSCRIPT CONTEXT:

{context}

CONVERSATION HISTORY:

{history_text}

CURRENT USER QUESTION:

{question}

ANSWER:
"""


    response = groq_client.chat.completions.create(

        model="openai/gpt-oss-20b",

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]

    )


    return (
        response
        .choices[0]
        .message.content
    )


# --------------------------------------------------
# Generate Summary
# --------------------------------------------------

def generate_summary(chunks):

    context = "\n\n".join(
        chunk["text"]
        for chunk in chunks
    )


    prompt = f"""
You are a YouTube video assistant.

Summarize the video transcript provided below.

Rules:
- Summarize only the information present in the transcript.
- Do not use outside knowledge.
- Give a clear and concise summary.
- Focus on the main ideas and important points.
- Do not mention timestamps or citations.
- If the transcript does not contain enough information, say so.

VIDEO TRANSCRIPT:

{context}

SUMMARY:
"""


    response = groq_client.chat.completions.create(

        model="openai/gpt-oss-20b",

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],

        temperature=0
    )


    return (
        response
        .choices[0]
        .message.content
        .strip()
    )


# --------------------------------------------------
# Get Cached RAG Data
# --------------------------------------------------

# --------------------------------------------------
# RAG Data (built from transcript sent by the extension)
# --------------------------------------------------

def has_rag_data(video_id: str) -> bool:
    return video_id in rag_cache


def build_rag_data(video_id, transcript):

    chunks = create_chunks(transcript)

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="No usable transcript content was found."
        )

    print(f"Created {len(chunks)} chunks.")

    index = create_vector_store(chunks)

    rag_cache[video_id] = {
        "chunks": chunks,
        "index": index
    }

    print(f"RAG data cached for video: {video_id}")

    return rag_cache[video_id]


def store_transcript(video_id, segments, language_code="en"):

    snippets = [
        Snippet(
            text=s.text.strip(),
            start=float(s.start),
            duration=float(s.duration)
        )
        for s in segments
        if s.text and s.text.strip()
    ]

    if not snippets:
        raise HTTPException(
            status_code=404,
            detail="The transcript was empty."
        )

    if not language_code.lower().startswith("en"):
        print(
            f"Using Groq to translate "
            f"{language_code} → English..."
        )
        snippets = translate_transcript_to_english(snippets)
        print("Groq translation successful.")

    build_rag_data(video_id, snippets)

    return len(snippets)


def get_rag_data(video_id):

    if video_id in rag_cache:

        print(
            f"Using cached RAG data "
            f"for video: {video_id}"
        )

        return rag_cache[video_id]

    # Transcript now comes from the extension, never from this server
    raise HTTPException(
        status_code=409,
        detail="TRANSCRIPT_NEEDED"
    )

