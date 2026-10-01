
from pathlib import Path
from dotenv import load_dotenv
import os

from fastapi import HTTPException
from groq import Groq

from sentence_transformers import SentenceTransformer
import faiss

from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)

from youtube_transcript_api._transcripts import (
    FetchedTranscript,
    FetchedTranscriptSnippet
)


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
# Translate Transcript to English
# --------------------------------------------------

def translate_transcript_to_english(transcript):

    translated_transcript = []

    batch = []
    batch_start = None
    batch_duration = 0

    max_chars = 5000

    for item in transcript:

        if batch_start is None:
            batch_start = item.start

        batch.append(item.text)

        batch_duration += item.duration

        current_text = " ".join(batch)

        if len(current_text) >= max_chars:

            prompt = f"""
Translate the following transcript into natural English.

Rules:
- Translate only.
- Do not summarize.
- Do not add information.
- Preserve the original meaning.
- Return only the English translation.

Transcript:
{current_text}
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

            translated_text = (
                response.choices[0]
                .message.content
                .strip()
            )

            translated_transcript.append(
                {
                    "text": translated_text,
                    "start": batch_start,
                    "duration": batch_duration
                }
            )

            batch = []
            batch_start = None
            batch_duration = 0


    # --------------------------------------------------
    # Translate Remaining Text
    # --------------------------------------------------

    if batch:

        current_text = " ".join(batch)

        prompt = f"""
Translate the following transcript into natural English.

Rules:
- Translate only.
- Do not summarize.
- Do not add information.
- Preserve the original meaning.
- Return only the English translation.

Transcript:
{current_text}
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

        translated_text = (
            response.choices[0]
            .message.content
            .strip()
        )

        translated_transcript.append(
            {
                "text": translated_text,
                "start": batch_start,
                "duration": batch_duration
            }
        )


    return FetchedTranscript(
        snippets=[
            FetchedTranscriptSnippet(
                text=item["text"],
                start=item["start"],
                duration=item["duration"]
            )
            for item in translated_transcript
        ],
        language="English",
        language_code="en",
        is_generated=False,
        video_id=""
    )


# --------------------------------------------------
# Get Transcript
# --------------------------------------------------

def fetch_transcript(video_id: str):

    try:

        api = YouTubeTranscriptApi()


        # --------------------------------------------
        # 1. Try English First
        # --------------------------------------------

        try:

            transcript = api.fetch(
                video_id,
                languages=["en"]
            )

            return transcript

        except NoTranscriptFound:

            print(
                "English transcript not found."
            )


        # --------------------------------------------
        # 2. Get Available Transcripts
        # --------------------------------------------

        transcript_list = api.list(
            video_id
        )


        print("\nAVAILABLE TRANSCRIPTS:")

        for transcript in transcript_list:

            print(
                "Language:",
                transcript.language,
                "| Code:",
                transcript.language_code,
                "| Generated:",
                transcript.is_generated,
                "| Translatable:",
                transcript.is_translatable,
                "| Translation languages:",
                [
                    lang.language_code
                    for lang in transcript.translation_languages
                ]
            )


        # --------------------------------------------
        # 3. Try Non-English Transcript
        # --------------------------------------------

        for transcript in transcript_list:

            if transcript.language_code == "en":
                continue

            print(
                f"Found transcript: "
                f"{transcript.language} "
                f"({transcript.language_code})"
            )

            print(
                f"Translatable: "
                f"{transcript.is_translatable}"
            )


            # ----------------------------------------
            # YouTube Translation First
            # ----------------------------------------

            if transcript.is_translatable:

                supported_languages = [
                    language.language_code
                    for language
                    in transcript.translation_languages
                ]

                if "en" in supported_languages:

                    try:

                        print(
                            f"Trying YouTube translation: "
                            f"{transcript.language} → English..."
                        )

                        translated_transcript = (
                            transcript
                            .translate("en")
                            .fetch()
                        )

                        print(
                            "YouTube translation successful."
                        )

                        return translated_transcript

                    except Exception as error:

                        print(
                            "YouTube translation failed:",
                            repr(error)
                        )

                        print(
                            "Falling back to Groq..."
                        )

            else:

                print(
                    "YouTube translation is not available."
                )


            # ----------------------------------------
            # Groq Translation Fallback
            # ----------------------------------------

            print(
                f"Using Groq to translate "
                f"{transcript.language} → English..."
            )

            original_transcript = (
                transcript.fetch()
            )

            translated_transcript = (
                translate_transcript_to_english(
                    original_transcript
                )
            )

            print(
                "Groq translation successful."
            )

            return translated_transcript


        # --------------------------------------------
        # Nothing Usable Found
        # --------------------------------------------

        raise HTTPException(
            status_code=404,
            detail=(
                "No English transcript or translatable "
                "transcript was available for this video."
            )
        )


    except TranscriptsDisabled:

        raise HTTPException(
            status_code=404,
            detail="Captions are disabled for this video."
        )


    except VideoUnavailable:

        raise HTTPException(
            status_code=404,
            detail="This YouTube video is unavailable."
        )


    except HTTPException:

        raise


    except Exception as error:

        print(
            "Transcript error:",
            repr(error)
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve the transcript."
        )


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

def get_rag_data(video_id):

    # --------------------------------------------
    # Check Cache First
    # --------------------------------------------

    if video_id in rag_cache:

        print(
            f"Using cached RAG data "
            f"for video: {video_id}"
        )

        return rag_cache[video_id]


    print(
        f"Creating new RAG data "
        f"for video: {video_id}"
    )


    # --------------------------------------------
    # 1. Get Transcript
    # --------------------------------------------

    transcript = fetch_transcript(
        video_id
    )


    # --------------------------------------------
    # 2. Create Chunks
    # --------------------------------------------

    chunks = create_chunks(
        transcript
    )


    if not chunks:

        raise HTTPException(
            status_code=404,
            detail="No usable transcript content was found."
        )


    print(
        f"Created {len(chunks)} chunks."
    )


    # --------------------------------------------
    # 3. Create FAISS Vector Store
    # --------------------------------------------

    index = create_vector_store(
        chunks
    )


    # --------------------------------------------
    # 4. Cache RAG Data
    # --------------------------------------------

    rag_data = {
        "chunks": chunks,
        "index": index
    }


    rag_cache[video_id] = rag_data


    print(
        f"RAG data cached for video: "
        f"{video_id}"
    )


    return rag_data
