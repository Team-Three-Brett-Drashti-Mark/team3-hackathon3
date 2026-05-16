from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.main import build_graph, PathwiseState


# =============================================================================
# FastAPI App
# =============================================================================

app = FastAPI(title="Pathwise API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Build the graph once at startup — shared across all requests
graph = build_graph()


class ChatRequest(BaseModel):
    user_input: str
    lesson_context: str = ""
    attempt: int = 1


class ChatResponse(BaseModel):
    response_text: str
    intent: str
    attempt: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Invokes the LangGraph pipeline and returns a guardrail-filtered response.
    The client tracks and sends `attempt` so the escalation persists across turns.
    """
    result = graph.invoke(
        PathwiseState(
            user_input=req.user_input,
            lesson_context=req.lesson_context,
            retrieved_chunks=[],
            intent="",
            attempt=req.attempt,
            response_text="",
        )
    )
    return ChatResponse(
        response_text=result["response_text"],
        intent=result["intent"],
        attempt=req.attempt,
    )
