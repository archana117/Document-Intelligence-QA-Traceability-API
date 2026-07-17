from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import init_db
from app.routes import router

app = FastAPI(
    title="CardioTrack CT-200 Document Parser & QA Traceability API",
    description="Hierarchical manual parser, version control, and selection-pinned LLM QA test case generation.",
    version="1.0.0"
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def on_startup():
    init_db()

# Include routes
app.include_router(router)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the CardioTrack CT-200 Parser & QA Traceability API!",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
