
######################
import json
import ast
import operator
import os

from dotenv import load_dotenv
from groq import Groq
from tavily import TavilyClient
from typing import TypedDict, Annotated

from langgraph.graph import StateGraph, START, END

from rag import (
    get_rag_data,
    retrieve_chunks,
    keyword_retrieve_chunks,
    generate_summary
)


# --------------------------------------------------
# Environment
# --------------------------------------------------

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("Groq key is missing from .env")

groq_client = Groq(
    api_key=GROQ_API_KEY
)


TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not TAVILY_API_KEY:
    raise ValueError("Tavily key is missing from .env")

tavily_client = TavilyClient(
    api_key=TAVILY_API_KEY
)


# --------------------------------------------------
# Router State
# --------------------------------------------------

class RouterState(TypedDict, total=False):

    question: str
    video_id: str
    history: list
    messages: Annotated[list, operator.add] 
    route: str
    final_route: str

    result: str
    retrieved_chunks: list
    tool_rounds: int
    flow: Annotated[list, operator.add] 
    web_sources: list          # NEW
# ---------------------
# Tools
# ----------------------
def youtube_rag_tool(
    video_id: str,
    query: str
    ):
    print(
        f"TOOL → youtube_rag("
        f"query={query})"
    )

    rag_data = get_rag_data(video_id)

    chunks = rag_data["chunks"]
    index = rag_data["index"]

    retrieved = retrieve_chunks(
        query,
        chunks,
        index,
        top_k=4
    )

    return retrieved

def keyword_retriever_tool(
    video_id: str,
    query: str
    ):
    print(
        f"TOOL → keyword_retriever("
        f"query={query})"
    )

    rag_data = get_rag_data(video_id)

    chunks = rag_data["chunks"]

    retrieved = keyword_retrieve_chunks(
        query,
        chunks,
        top_k=4
    )

    return retrieved

def web_search_tool(query: str):

    search_results = tavily_client.search(
        query=query,
        search_depth="basic",
        max_results=5
    )

    results_text = []
    sources = []

    for result in search_results["results"]:

        results_text.append(
            f"Title: {result.get('title', '')}\n"
            f"URL: {result.get('url', '')}\n"
            f"Content: {result.get('content', '')}"
        )

        sources.append({
            "title": result.get("title", ""),
            "url": result.get("url", "")
        })

    return "\n\n".join(results_text), sources

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_calculate_node(node):

    if isinstance(node, ast.Constant):

        if isinstance(
            node.value,
            (int, float)
        ):
            return node.value

        raise ValueError(
            "Only numbers are allowed."
        )

    if isinstance(
        node,
        ast.UnaryOp
    ):

        operator_function = _ALLOWED_OPERATORS.get(
            type(node.op)
        )

        if not operator_function:
            raise ValueError(
                "Unsupported operator."
            )

        return operator_function(
            _safe_calculate_node(node.operand)
        )

    if isinstance(
        node,
        ast.BinOp
    ):

        operator_function = _ALLOWED_OPERATORS.get(
            type(node.op)
        )

        if not operator_function:
            raise ValueError(
                "Unsupported operator."
            )

        return operator_function(
            _safe_calculate_node(node.left),
            _safe_calculate_node(node.right)
        )

    raise ValueError(
        "Invalid mathematical expression."
    )


def calculator_tool(
    expression: str
    ):

    print(
        f"TOOL → calculator("
        f"expression={expression})"
    )

    try:

        tree = ast.parse(
            expression,
            mode="eval"
        )

        result = _safe_calculate_node(
            tree.body
        )

        return str(result)

    except Exception as error:

        return (
            f"Calculator error: {error}"
        )

def summarize_tool(video_id: str):
    print("TOOL → summarize_video")
    chunks = get_rag_data(video_id)["chunks"]
    if not chunks:
        return "No transcript content available."
    return generate_summary(chunks)
TOOLS = [

    {
        "type": "function",
        "function": {
            "name": "youtube_rag",
            "description": (
                "Search the current YouTube video's "
                "transcript using semantic FAISS retrieval. "
                "Use this when the question may be answered "
                "from the video's content."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    
                    "query": {
                        "type": "string",
                        "description": (
                            "The information to search for "
                            "in the video transcript."
                        )
                    }
                },
                "required": [
                    "query"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "keyword_retriever",
            "description": (
                "Search the current YouTube transcript "
                "using direct keyword matching. "
                "Use this when semantic retrieval may miss "
                "exact terminology or names."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    
                    "query": {
                        "type": "string",
                        "description": (
                            "Keywords or phrase to find "
                            "in the transcript."
                        )
                    }
                },
                "required": [
                    
                    "query"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Search the internet for information "
                "not available in the YouTube transcript, "
                "including general or current information."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "The web search query."
                        )
                    }
                },
                "required": [
                    "query"
                ]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Perform mathematical calculations. "
                "Use this instead of calculating arithmetic "
                "yourself."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": (
                            "A mathematical expression such "
                            "as 25 * 4 + 10."
                        )
                    }
                },
                "required": [
                    "expression"
                ]
            }
        }
    },
    {
    "type": "function",
    "function": {
        "name": "summarize_video",
        "description": (
            "Summarize the whole current video. "
            "Use when asked for an overall summary."
        ),
        "parameters": {"type": "object", "properties": {}}
    }
   }
]
# --------------------------------------------------
# Router Node
# --------------------------------------------------

MAX_TOOL_ROUNDS = 5

SYSTEM_PROMPT = """
You are an agentic YouTube AI assistant. The user is watching a
specific YouTube video, and their questions are about THAT video
unless they clearly say otherwise.

You have five tools:
1. youtube_rag - semantic search of the video transcript
2. keyword_retriever - exact keyword search of the transcript
3. web_search - search the internet
4. calculator - arithmetic
5. summarize_video - summarize the whole video

Rules:
- Call youtube_rag FIRST for any question. Rewrite short or vague
  questions into a clear search query.
- If youtube_rag finds nothing, try keyword_retriever.
- If BOTH transcript tools find nothing relevant, you MUST call
  web_search. Never give up without trying web_search.
- When calling web_search, write a complete standalone query
  (e.g. "what is RAG in AI", not just "RAG").
- If the answer came from the transcript, use ONLY the transcript
  passages.
- If the answer came from web_search, start with one short sentence
  saying the video doesn't cover it, then answer from the web results.
- Use summarize_video for overall summaries.
- Use calculator for arithmetic.
- Do not mention internal tools. Do not invent information.
- If the user asks about the conversation itself (for example
  "summarize what we talked about" or "what did I ask before"),
  answer directly from the conversation history without calling
  any tool.
"""
def tool_node(state: RouterState):

    last_message = state["messages"][-1]
    video_id = state["video_id"]          # injected from state, not from the LLM

    tool_results = []
    retrieved_chunks = state.get("retrieved_chunks", [])
    web_sources = state.get("web_sources", [])
    for tool_call in last_message.get("tool_calls", []):

        tool_name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"] or "{}")

        try:
            if tool_name in ("youtube_rag", "keyword_retriever"):

                fn = (
                    youtube_rag_tool
                    if tool_name == "youtube_rag"
                    else keyword_retriever_tool
                )
                result = fn(video_id, arguments["query"])

                if result:
                    retrieved_chunks = result
                    web_sources = []            # NEW
                    tool_content = json.dumps(result)
                else:
                    tool_content = "No relevant transcript passages found."

            elif tool_name == "web_search":

                tool_content, web_sources = web_search_tool(arguments["query"])
                retrieved_chunks = []
                log(f"   ↳ web_search: {len(web_sources)} source(s) received")

            elif tool_name == "calculator":
                tool_content = calculator_tool(arguments["expression"])

            elif tool_name == "summarize_video":
                tool_content = summarize_tool(video_id)
                retrieved_chunks = []
                web_sources = []            # NEW

            else:
                tool_content = f"Unknown tool: {tool_name}"

        except Exception as error:
            tool_content = f"Tool error: {str(error)}"

        tool_results.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": tool_name,
            "content": str(tool_content)
        })

    return {
        "messages": tool_results,
        "retrieved_chunks": retrieved_chunks,
        "tool_rounds": state.get("tool_rounds", 0) + 1
    }
def log(message: str):
    print(f"[FLOW] {message}", flush=True)

def agent_node(state: RouterState):

    messages = list(state.get("messages", []))
    new_messages = []
    rounds = state.get("tool_rounds", 0)

    if not messages:

        log("START → agent")
        log(f"Question: {state['question']}")

        new_messages.append({"role": "system", "content": SYSTEM_PROMPT})

        for item in state.get("history", []):
            new_messages.append({
                "role": "user" if item.role == "user" else "assistant",
                "content": item.content
            })

        new_messages.append({"role": "user", "content": state["question"]})
        messages = list(new_messages)

    else:
        log(f"tools → agent (round {rounds})")

    log("AGENT: thinking...")

        # ---- inspect what the tools have returned so far ----
    tool_msgs = [m for m in messages if m.get("role") == "tool"]

    def was_empty(name):
        return any(
            m["name"] == name and m["content"].startswith("No relevant")
            for m in tool_msgs
        )

    web_used = any(m["name"] == "web_search" for m in tool_msgs)

    both_empty = was_empty("youtube_rag") and was_empty("keyword_retriever")

    if rounds == 0:
        tool_choice = "required"
    elif both_empty and not web_used and rounds < MAX_TOOL_ROUNDS:
        # transcript had nothing → force web search
        tool_choice = {
            "type": "function",
            "function": {"name": "web_search"}
        }
        log("GUARD: transcript empty → forcing web_search")
    elif rounds < MAX_TOOL_ROUNDS:
        tool_choice = "auto"
    else:
        tool_choice = "none"

    def call_model(choice):
        return groq_client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=messages,
            tools=TOOLS,
            tool_choice=choice,
            temperature=0
        )

    try:
        response = call_model(tool_choice)

    except Exception as error:

        # The model wanted to answer without a tool while a tool was forced
        if "tool_use_failed" in str(error) or "Tool choice is required" in str(error):
            log("GUARD: no tool needed for this question → retrying with auto")
            response = call_model("auto")
        else:
            raise

    message = response.choices[0].message

    assistant_message = {
        "role": "assistant",
        "content": message.content or ""
    }

    update = {}

    if message.tool_calls:

        assistant_message["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            }
            for tc in message.tool_calls
        ]

        names = [tc.function.name for tc in message.tool_calls]

        log(f"AGENT decided: need tool(s) → {names}")
        update["flow"] = [f"agent→{n}" for n in names]

    else:

        log("AGENT decided: no more tools needed → final answer")
        update["result"] = message.content or ""
        update["flow"] = ["agent→answer"]

    new_messages.append(assistant_message)
    update["messages"] = new_messages

    return update
def tool_node(state: RouterState):

    last_message = state["messages"][-1]
    video_id = state["video_id"]

    tool_results = []
    retrieved_chunks = state.get("retrieved_chunks", [])
    web_sources = state.get("web_sources", [])
    for tool_call in last_message.get("tool_calls", []):

        tool_name = tool_call["function"]["name"]
        arguments = json.loads(tool_call["function"]["arguments"] or "{}")

        log(f"TOOL NODE: running '{tool_name}' with args {arguments}")

        try:

            if tool_name in ("youtube_rag", "keyword_retriever"):

                fn = (
                    youtube_rag_tool
                    if tool_name == "youtube_rag"
                    else keyword_retriever_tool
                )

                result = fn(video_id, arguments["query"])

                if result:
                    retrieved_chunks = result
                    tool_content = json.dumps(result)

                    scores = [
                        round(c.get("score", c.get("keyword_score", 0)), 3)
                        for c in result
                    ]
                    log(f"   ↳ {tool_name}: found {len(result)} chunk(s), scores={scores}")

                else:
                    tool_content = "No relevant transcript passages found."
                    log(f"   ↳ {tool_name}: NOTHING found → agent may try another tool")

            elif tool_name == "web_search":

                tool_content, web_sources = web_search_tool(arguments["query"])
                retrieved_chunks = []
                log(f"   ↳ web_search: {len(web_sources)} source(s) received")

            elif tool_name == "calculator":

                tool_content = calculator_tool(arguments["expression"])
                log(f"   ↳ calculator: result = {tool_content}")

            elif tool_name == "summarize_video":

                tool_content = summarize_tool(video_id)
                retrieved_chunks = []
                log("   ↳ summarize_video: summary generated")

            else:
                tool_content = f"Unknown tool: {tool_name}"
                log(f"   ↳ unknown tool: {tool_name}")

        except Exception as error:

            tool_content = f"Tool error: {str(error)}"
            log(f"   ↳ {tool_name} FAILED: {error}")

        tool_results.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "name": tool_name,
            "content": str(tool_content)
        })

    log("TOOL NODE finished → back to agent")

    return {
        "messages": tool_results,
        "retrieved_chunks": retrieved_chunks,
        "web_sources": web_sources,             # NEW
        "tool_rounds": state.get("tool_rounds", 0) + 1,
        "flow": [f"{r['name']}→agent" for r in tool_results]
    }
def should_continue(state: RouterState):

    last_message = state["messages"][-1]

    if last_message.get("tool_calls"):

        return "tools"

    return END


# --------------------------------------------------
# Build LangGraph
# --------------------------------------------------

def build_router():

    graph = StateGraph(RouterState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.add_edge(START, "agent")

    graph.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", END: END}
    )

    graph.add_edge("tools", "agent")

    return graph.compile()

# --------------------------------------------------
# Create Router
# --------------------------------------------------

router = build_router()