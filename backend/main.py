# -*- coding: utf-8 -*-
"""
LUMA — Backend Entry Point
===========================
Run with: uvicorn main:app --reload --port 8000

Then open: http://localhost:8000/docs
(FastAPI auto-generates interactive API documentation)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

app = FastAPI(
    title="LUMA API",
    description="Learning Universal Machine Architecture — Funeral Home Form Automation",
    version="0.1.0"
)

# Allow frontend to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(router)


@app.get("/")
def root():
    return {
        "service": "LUMA",
        "version": "0.1.0",
        "docs": "http://localhost:8000/docs",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
