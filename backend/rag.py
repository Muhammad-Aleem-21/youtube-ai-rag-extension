# from pathlib import Path
# from dotenv import load_dotenv
# import os

# from fastapi import HTTPException
# from groq import Groq

# from sentence_transformers import SentenceTransformer
# import faiss

# from youtube_transcript_api import (
#     YouTubeTranscriptApi,
#     TranscriptsDisabled,
#     NoTranscriptFound,
#     VideoUnavailable,
# )

# from youtube_transcript_api._transcripts import (
#     FetchedTranscript,
#     FetchedTranscriptSnippet
# )


# # --------------------------------------------------
# # Environment
# # --------------------------------------------------

# BASE_DIR = Path(__file__).resolve().parent

# load_dotenv(
#     BASE_DIR / ".env",
#     override=True
# )


# # --------------------------------------------------
# # Groq
# # --------------------------------------------------

# GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# if not GROQ_API_KEY:
#     raise ValueError(
#         "Groq key is missing from .env"
#     )

# groq_client = Groq(
#     api_key=GROQ_API_KEY
# )


# # --------------------------------------------------
# # Embedding Model
# # --------------------------------------------------

# print("Loading embedding model...")

# embedding_model = SentenceTransformer(
#     "sentence-transformers/all-MiniLM-L6-v2"
# )

# print("Embedding model loaded.")


# # --------------------------------------------------
# # RAG Cache
# # --------------------------------------------------

# rag_cache = {}


# # --------------------------------------------------
# # Translate Transcript to English
# # --------------------------------------------------

# def translate_transcript_to_english(transcript):

#     translated_transcript = []

#     batch = []
#     batch_start = None
#     batch_duration = 0

#     max_chars = 5000

#     for item in transcript:

#         if batch_start is None:
#             batch_start = item.start

#         batch.append(item.text)

#         batch_duration += item.duration

#         current_text = " ".join(batch)

#         if len(current_text) >= max_chars:

#             prompt = f"""
# Translate the following transcript into natural English.

# Rules:
# - Translate only.
# - Do not summarize.
# - Do not add information.
# - Preserve the original meaning.
# - Return only the English translation.

# Transcript:
# {current_text}
# """

#             response = groq_client.chat.completions.create(
#                 model="openai/gpt-oss-20b",
#                 messages=[
#                     {
#                         "role": "user",
#                         "content": prompt
#                     }
#                 ]
#             )

#             translated_text = (
#                 response.choices[0]
#                 .message.content
#                 .strip()
#             )

#             translated_transcript.append(
#                 {
#                     "text": translated_text,
#                     "start": batch_start,
#                     "duration": batch_duration
#                 }
#             )

#             batch = []
#             batch_start = None
#             batch_duration = 0


#     # --------------------------------------------------
#     # Translate Remaining Text
#     # --------------------------------------------------

#     if batch:

#         current_text = " ".join(batch)

#         prompt = f"""
# Translate the following transcript into natural English.

# Rules:
# - Translate only.
# - Do not summarize.
# - Do not add information.
# - Preserve the original meaning.
# - Return only the English translation.

# Transcript:
# {current_text}
# """

#         response = groq_client.chat.completions.create(
#             model="openai/gpt-oss-20b",
#             messages=[
#                 {
#                     "role": "user",
#                     "content": prompt
#                 }
#             ]
#         )

#         translated_text = (
#             response.choices[0]
#             .message.content
#             .strip()
#         )

#         translated_transcript.append(
#             {
#                 "text": translated_text,
#                 "start": batch_start,
#                 "duration": batch_duration
#             }
#         )


#     return FetchedTranscript(
#         snippets=[
#             FetchedTranscriptSnippet(
#                 text=item["text"],
#                 start=item["start"],
#                 duration=item["duration"]
#             )
#             for item in translated_transcript
#         ],
#         language="English",
#         language_code="en",
#         is_generated=False,
#         video_id=""
#     )


# # --------------------------------------------------
# # Get Transcript
# # --------------------------------------------------

# def fetch_transcript(video_id: str):

#     try:

#         api = YouTubeTranscriptApi()


#         # --------------------------------------------
#         # 1. Try English First
#         # --------------------------------------------

#         try:

#             transcript = api.fetch(
#                 video_id,
#                 languages=["en"]
#             )

#             return transcript

#         except NoTranscriptFound:

#             print(
#                 "English transcript not found."
#             )


#         # --------------------------------------------
#         # 2. Get Available Transcripts
#         # --------------------------------------------

#         transcript_list = api.list(
#             video_id
#         )


#         print("\nAVAILABLE TRANSCRIPTS:")

#         for transcript in transcript_list:

#             print(
#                 "Language:",
#                 transcript.language,
#                 "| Code:",
#                 transcript.language_code,
#                 "| Generated:",
#                 transcript.is_generated,
#                 "| Translatable:",
#                 transcript.is_translatable,
#                 "| Translation languages:",
#                 [
#                     lang.language_code
#                     for lang in transcript.translation_languages
#                 ]
#             )


#         # --------------------------------------------
#         # 3. Try Non-English Transcript
#         # --------------------------------------------

#         for transcript in transcript_list:

#             if transcript.language_code == "en":
#                 continue

#             print(
#                 f"Found transcript: "
#                 f"{transcript.language} "
#                 f"({transcript.language_code})"
#             )

#             print(
#                 f"Translatable: "
#                 f"{transcript.is_translatable}"
#             )


#             # ----------------------------------------
#             # YouTube Translation First
#             # ----------------------------------------

#             if transcript.is_translatable:

#                 supported_languages = [
#                     language.language_code
#                     for language
#                     in transcript.translation_languages
#                 ]

#                 if "en" in supported_languages:

#                     try:

#                         print(
#                             f"Trying YouTube translation: "
#                             f"{transcript.language} → English..."
#                         )

#                         translated_transcript = (
#                             transcript
#                             .translate("en")
#                             .fetch()
#                         )

#                         print(
#                             "YouTube translation successful."
#                         )

#                         return translated_transcript

#                     except Exception as error:

#                         print(
#                             "YouTube translation failed:",
#                             repr(error)
#                         )

#                         print(
#                             "Falling back to Groq..."
#                         )

#             else:

#                 print(
#                     "YouTube translation is not available."
#                 )


#             # ----------------------------------------
#             # Groq Translation Fallback
#             # ----------------------------------------

#             print(
#                 f"Using Groq to translate "
#                 f"{transcript.language} → English..."
#             )

#             original_transcript = (
#                 transcript.fetch()
#             )

#             translated_transcript = (
#                 translate_transcript_to_english(
#                     original_transcript
#                 )
#             )

#             print(
#                 "Groq translation successful."
#             )

#             return translated_transcript


#         # --------------------------------------------
#         # Nothing Usable Found
#         # --------------------------------------------

#         raise HTTPException(
#             status_code=404,
#             detail=(
#                 "No English transcript or translatable "
#                 "transcript was available for this video."
#             )
#         )


#     except TranscriptsDisabled:

#         raise HTTPException(
#             status_code=404,
#             detail="Captions are disabled for this video."
#         )


#     except VideoUnavailable:

#         raise HTTPException(
#             status_code=404,
#             detail="This YouTube video is unavailable."
#         )


#     except HTTPException:

#         raise


#     except Exception as error:

#         print(
#             "Transcript error:",
#             repr(error)
#         )

#         raise HTTPException(
#             status_code=500,
#             detail="Unable to retrieve the transcript."
#         )


# # --------------------------------------------------
# # Create Transcript Chunks
# # --------------------------------------------------

# def create_chunks(transcript):

#     chunks = []

#     current_text = []
#     current_start = None
#     current_end = None

#     max_chars = 1000


#     for item in transcript:

#         text = item.text.strip()

#         if not text:
#             continue


#         if current_start is None:

#             current_start = item.start


#         current_text.append(text)

#         current_end = (
#             item.start +
#             item.duration
#         )

#         combined = " ".join(
#             current_text
#         )


#         if len(combined) >= max_chars:

#             chunks.append(
#                 {
#                     "text": combined,
#                     "start": current_start,
#                     "end": current_end
#                 }
#             )

#             current_text = []
#             current_start = None
#             current_end = None


#     # --------------------------------------------
#     # Add Remaining Text
#     # --------------------------------------------

#     if current_text:

#         chunks.append(
#             {
#                 "text": " ".join(current_text),
#                 "start": current_start,
#                 "end": current_end
#             }
#         )


#     return chunks


# # --------------------------------------------------
# # Create FAISS Vector Store
# # --------------------------------------------------

# def create_vector_store(chunks):

#     texts = [
#         chunk["text"]
#         for chunk in chunks
#     ]

#     embeddings = embedding_model.encode(
#         texts,
#         convert_to_numpy=True,
#         normalize_embeddings=True
#     )

#     dimension = embeddings.shape[1]

#     index = faiss.IndexFlatIP(
#         dimension
#     )

#     index.add(
#         embeddings.astype("float32")
#     )

#     return index


# # --------------------------------------------------
# # Retrieve Relevant Chunks
# # --------------------------------------------------

# def retrieve_chunks(
#     question,
#     chunks,
#     index,
#     top_k=4,
#     similarity_threshold=0.35
#  ):

#     question_embedding = (
#         embedding_model.encode(
#             [question],
#             convert_to_numpy=True,
#             normalize_embeddings=True
#         )
#     )


#     scores, indices = index.search(
#         question_embedding.astype(
#             "float32"
#         ),
#         min(
#             top_k,
#             len(chunks)
#         )
#     )


#     results = []


#     for score, idx in zip(
#         scores[0],
#         indices[0]
#     ):

#         if idx == -1:
#             continue


#         print(
#             f"Retrieved chunk score: "
#             f"{float(score):.4f} "
#             f"| Threshold: "
#             f"{similarity_threshold}"
#         )


#         if (
#             float(score) < similarity_threshold
#             and len(chunks) > 1
#         ):
#             continue


#         chunk = chunks[idx].copy()

#         chunk["score"] = float(
#             score
#         )

#         results.append(
#             chunk
#         )


#     return results

# ####
# def keyword_retrieve_chunks(
#     question,
#     chunks,
#     top_k=4
# ):
#     """
#     Second retriever using keyword overlap.
#     Useful when semantic similarity does not find
#     an obvious transcript match.
#     """

#     import re

#     question_words = set(
#         re.findall(
#             r"\b[a-zA-Z0-9]{3,}\b",
#             question.lower()
#         )
#     )

#     scored_chunks = []

#     for chunk in chunks:

#         chunk_words = set(
#             re.findall(
#                 r"\b[a-zA-Z0-9]{3,}\b",
#                 chunk["text"].lower()
#             )
#         )

#         overlap = question_words.intersection(
#             chunk_words
#         )

#         if not overlap:
#             continue

#         score = len(overlap) / max(
#             len(question_words),
#             1
#         )

#         result = chunk.copy()

#         result["keyword_score"] = score
#         result["matched_keywords"] = list(overlap)

#         scored_chunks.append(result)

#     scored_chunks.sort(
#         key=lambda x: x["keyword_score"],
#         reverse=True
#     )

#     return scored_chunks[:top_k]
# # --------------------------------------------------
# # Generate RAG Answer
# # --------------------------------------------------

# def generate_answer(
#     question,
#     retrieved_chunks,
#     history
# ):

#     context_parts = []


#     for chunk in retrieved_chunks:

#         minutes = int(
#             chunk["start"] // 60
#         )

#         seconds = int(
#             chunk["start"] % 60
#         )

#         timestamp = (
#             f"{minutes}:{seconds:02d}"
#         )


#         context_parts.append(
#             f"[Timestamp: {timestamp}]\n"
#             f"{chunk['text']}"
#         )


#     context = "\n\n".join(
#         context_parts
#     )


#     history_text = ""


#     if history:

#         history_parts = []


#         for message in history[-6:]:

#             history_parts.append(
#                 f"{message.role}: "
#                 f"{message.content}"
#             )


#         history_text = "\n".join(
#             history_parts
#         )


#     prompt = f"""
# You are a YouTube video assistant.

# Answer the user's question using ONLY the transcript context provided below.

# You may use the conversation history to understand references such as:
# "it", "that", "this", "he", "she", or "the previous point".

# Do NOT use outside knowledge.

# If the transcript does not contain enough information to answer,
# say that you don't know based on the video transcript.

# Do NOT include timestamps, source references, citations,
# or phrases such as "Referenced from timestamps" in your answer.
# The application will display the source separately.

# TRANSCRIPT CONTEXT:

# {context}

# CONVERSATION HISTORY:

# {history_text}

# CURRENT USER QUESTION:

# {question}

# ANSWER:
# """


#     response = groq_client.chat.completions.create(

#         model="openai/gpt-oss-20b",

#         messages=[
#             {
#                 "role": "user",
#                 "content": prompt
#             }
#         ]

#     )


#     return (
#         response
#         .choices[0]
#         .message.content
#     )


# # --------------------------------------------------
# # Generate Summary
# # --------------------------------------------------

# def generate_summary(chunks):

#     context = "\n\n".join(
#         chunk["text"]
#         for chunk in chunks
#     )


#     prompt = f"""
# You are a YouTube video assistant.

# Summarize the video transcript provided below.

# Rules:
# - Summarize only the information present in the transcript.
# - Do not use outside knowledge.
# - Give a clear and concise summary.
# - Focus on the main ideas and important points.
# - Do not mention timestamps or citations.
# - If the transcript does not contain enough information, say so.

# VIDEO TRANSCRIPT:

# {context}

# SUMMARY:
# """


#     response = groq_client.chat.completions.create(

#         model="openai/gpt-oss-20b",

#         messages=[
#             {
#                 "role": "user",
#                 "content": prompt
#             }
#         ],

#         temperature=0
#     )


#     return (
#         response
#         .choices[0]
#         .message.content
#         .strip()
#     )


# # --------------------------------------------------
# # Get Cached RAG Data
# # --------------------------------------------------

# def get_rag_data(video_id):

#     # --------------------------------------------
#     # Check Cache First
#     # --------------------------------------------

#     if video_id in rag_cache:

#         print(
#             f"Using cached RAG data "
#             f"for video: {video_id}"
#         )

#         return rag_cache[video_id]


#     print(
#         f"Creating new RAG data "
#         f"for video: {video_id}"
#     )


#     # --------------------------------------------
#     # 1. Get Transcript
#     # --------------------------------------------

#     transcript = fetch_transcript(
#         video_id
#     )


#     # --------------------------------------------
#     # 2. Create Chunks
#     # --------------------------------------------

#     chunks = create_chunks(
#         transcript
#     )


#     if not chunks:

#         raise HTTPException(
#             status_code=404,
#             detail="No usable transcript content was found."
#         )


#     print(
#         f"Created {len(chunks)} chunks."
#     )


#     # --------------------------------------------
#     # 3. Create FAISS Vector Store
#     # --------------------------------------------

#     index = create_vector_store(
#         chunks
#     )


#     # --------------------------------------------
#     # 4. Cache RAG Data
#     # --------------------------------------------

#     rag_data = {
#         "chunks": chunks,
#         "index": index
#     }


#     rag_cache[video_id] = rag_data


#     print(
#         f"RAG data cached for video: "
#         f"{video_id}"
#     )


#     return rag_data

###########################3
import hashlib
import os
import re
import threading
from collections import OrderedDict

import faiss
import numpy as np
from groq import Groq
from sentence_transformers import SentenceTransformer

# --------------------------------------------------
# Configuration
# --------------------------------------------------

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "openai/gpt-oss-20b")

CHUNK_TARGET_CHARS = 900
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "0.25"))
MAX_CACHED_VIDEOS = int(os.getenv("MAX_CACHED_VIDEOS", "50"))
MAX_TRANSCRIPT_CHARS = 1_500_000

SINGLE_PASS_CHARS = 12_000
MAX_SUMMARY_BATCHES = 10


class TranscriptNotLoadedError(Exception):
    """Raised when no browser-provided transcript is cached for a video."""


# --------------------------------------------------
# Lazy singletons
# --------------------------------------------------

_embedder = None
_embedder_lock = threading.Lock()

_groq_client = None
_groq_lock = threading.Lock()


def get_embedder():
    global _embedder
    if _embedder is None:
        with _embedder_lock:
            if _embedder is None:
                print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}", flush=True)
                _embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
    return _embedder


def get_groq():
    global _groq_client
    if _groq_client is None:
        with _groq_lock:
            if _groq_client is None:
                key = os.getenv("GROQ_API_KEY")
                if not key:
                    raise ValueError("GROQ_API_KEY is missing")
                _groq_client = Groq(api_key=key)
    return _groq_client


def _embed(texts):
    vectors = get_embedder().encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
        batch_size=64,
    )
    return np.ascontiguousarray(vectors.astype("float32"))


# --------------------------------------------------
# Transcript normalization (browser-provided data)
# --------------------------------------------------

def normalize_transcript(raw_segments):
    """
    Validate/clean browser-provided segments into
    [{"text": str, "start": float, "duration": float}, ...] sorted by start.
    Raises ValueError if nothing usable remains.
    """
    cleaned = []
    total_chars = 0

    for seg in raw_segments or []:
        if not isinstance(seg, dict):
            continue

        text = re.sub(r"\s+", " ", str(seg.get("text", ""))).strip()
        if not text:
            continue

        try:
            start = float(seg.get("start", 0))
            duration = float(seg.get("duration", 0) or 0)
        except (TypeError, ValueError):
            continue

        if start != start or start < 0:  # NaN or negative
            continue
        if duration != duration or duration < 0:
            duration = 0.0

        total_chars += len(text)
        if total_chars > MAX_TRANSCRIPT_CHARS:
            raise ValueError("Transcript is too large.")

        cleaned.append({"text": text, "start": start, "duration": duration})

    if not cleaned:
        raise ValueError("Transcript contains no usable text.")

    cleaned.sort(key=lambda s: s["start"])
    return cleaned


# --------------------------------------------------
# Chunking + vector store
# --------------------------------------------------

def create_chunks(transcript):
    chunks = []
    buffer = []
    buffer_chars = 0

    def flush():
        nonlocal buffer, buffer_chars
        if not buffer:
            return
        last = buffer[-1]
        chunks.append({
            "chunk_id": len(chunks),
            "text": " ".join(s["text"] for s in buffer),
            "start": buffer[0]["start"],
            "end": last["start"] + last["duration"],
        })
        buffer = []
        buffer_chars = 0

    for seg in transcript:
        buffer.append(seg)
        buffer_chars += len(seg["text"]) + 1
        if buffer_chars >= CHUNK_TARGET_CHARS:
            flush()

    flush()
    return chunks


def create_vector_store(chunks):
    vectors = _embed([c["text"] for c in chunks])
    index = faiss.IndexFlatIP(vectors.shape[1])  # cosine (vectors are normalized)
    index.add(vectors)
    return index


# --------------------------------------------------
# Retrieval
# --------------------------------------------------

def retrieve_chunks(query, chunks, index, top_k=4):
    if not chunks:
        return []

    query_vector = _embed([query])
    scores, ids = index.search(query_vector, min(top_k, len(chunks)))

    results = []
    for score, idx in zip(scores[0], ids[0]):
        if idx < 0 or float(score) < RELEVANCE_THRESHOLD:
            continue
        item = dict(chunks[idx])
        item["score"] = float(score)
        results.append(item)

    return results


_STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "what", "when", "where", "which",
    "who", "whom", "how", "why", "does", "did", "this", "that", "these", "those",
    "with", "about", "from", "into", "video", "say", "says", "said", "tell",
    "you", "your", "can", "could", "would", "should", "have", "has", "had",
}


def keyword_retrieve_chunks(query, chunks, top_k=4):
    tokens = [
        t for t in re.findall(r"[a-z0-9]+", query.lower())
        if len(t) > 2 and t not in _STOPWORDS
    ]
    if not tokens or not chunks:
        return []

    scored = []
    for chunk in chunks:
        words = set(re.findall(r"[a-z0-9]+", chunk["text"].lower()))
        matched = sum(1 for t in tokens if t in words)
        if matched:
            scored.append((matched / len(tokens), chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    results = []
    for score, chunk in scored[:top_k]:
        item = dict(chunk)
        item["keyword_score"] = float(score)
        results.append(item)
    return results


# --------------------------------------------------
# Summary
# --------------------------------------------------

def _llm(system_prompt, user_prompt):
    response = get_groq().chat.completions.create(
        model=SUMMARY_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""


def generate_summary(chunks):
    texts = [c["text"] for c in chunks]
    full_text = " ".join(texts)

    system = (
        "You summarize YouTube video transcripts accurately. "
        "Use only the provided text. Do not invent information."
    )

    if len(full_text) <= SINGLE_PASS_CHARS:
        return _llm(
            system,
            "Write a clear, well-structured summary of this video transcript. "
            "Start with one sentence on the main topic, then list the key points.\n\n"
            f"Transcript:\n{full_text}",
        )

    batch_chars = max(8000, len(full_text) // MAX_SUMMARY_BATCHES + 1)
    batches, current, size = [], [], 0
    for text in texts:
        current.append(text)
        size += len(text) + 1
        if size >= batch_chars:
            batches.append(" ".join(current))
            current, size = [], 0
    if current:
        batches.append(" ".join(current))

    partials = []
    for i, batch in enumerate(batches, start=1):
        partials.append(_llm(
            system,
            f"Summarize part {i} of {len(batches)} of a video transcript "
            f"in a few concise bullet points.\n\n{batch}",
        ))

    return _llm(
        system,
        "Below are summaries of consecutive parts of one video. "
        "Combine them into one clear, well-structured summary of the whole video. "
        "Start with one sentence on the main topic, then list the key points.\n\n"
        + "\n\n".join(f"Part {i}:\n{p}" for i, p in enumerate(partials, start=1)),
    )


# --------------------------------------------------
# RAG cache (populated ONLY from browser-provided transcripts)
# --------------------------------------------------

_rag_cache = OrderedDict()
_cache_lock = threading.Lock()


def _describe(rag_data, cached):
    return {
        "segments": rag_data["segment_count"],
        "chunks": len(rag_data["chunks"]),
        "language": rag_data.get("language"),
        "language_code": rag_data.get("language_code"),
        "is_generated": rag_data.get("is_generated"),
        "cached": cached,
    }


def store_transcript(
    cache_key,
    raw_segments,
    language=None,
    language_code=None,
    is_generated=None,
):
    """
    Build chunks + FAISS index from a browser-provided transcript and cache it.
    If an identical transcript is already cached, do nothing.
    """
    segments = normalize_transcript(raw_segments)

    fingerprint = hashlib.sha256(
        "\n".join(f"{s['start']:.2f}|{s['text']}" for s in segments).encode("utf-8")
    ).hexdigest()

    with _cache_lock:
        existing = _rag_cache.get(cache_key)
        if existing and existing["fingerprint"] == fingerprint:
            _rag_cache.move_to_end(cache_key)
            return _describe(existing, cached=True)

    print(f"Creating RAG data for {cache_key} from browser transcript "
          f"({len(segments)} segments)", flush=True)

    chunks = create_chunks(segments)
    index = create_vector_store(chunks)

    rag_data = {
        "chunks": chunks,
        "index": index,
        "fingerprint": fingerprint,
        "segment_count": len(segments),
        "language": language,
        "language_code": language_code,
        "is_generated": is_generated,
    }

    with _cache_lock:
        _rag_cache[cache_key] = rag_data
        _rag_cache.move_to_end(cache_key)
        while len(_rag_cache) > MAX_CACHED_VIDEOS:
            _rag_cache.popitem(last=False)

    return _describe(rag_data, cached=False)


def has_rag_data(cache_key):
    with _cache_lock:
        return cache_key in _rag_cache


def get_rag_status(cache_key):
    with _cache_lock:
        rag_data = _rag_cache.get(cache_key)
        if not rag_data:
            return None
        _rag_cache.move_to_end(cache_key)
        return _describe(rag_data, cached=True)


def get_rag_data(cache_key, transcript_data=None):
    """
    Return cached RAG data.

    transcript_data (optional) is a dict with a "transcript" list and optional
    "language", "language_code", "is_generated". If supplied, it is used to
    build the cache entry. This function NEVER contacts YouTube.
    """
    if transcript_data is not None:
        store_transcript(
            cache_key,
            transcript_data.get("transcript"),
            transcript_data.get("language"),
            transcript_data.get("language_code"),
            transcript_data.get("is_generated"),
        )

    with _cache_lock:
        rag_data = _rag_cache.get(cache_key)
        if rag_data is not None:
            _rag_cache.move_to_end(cache_key)
            return rag_data

    raise TranscriptNotLoadedError(
        "No transcript has been loaded for this video. "
        "The browser must send it first."
    )