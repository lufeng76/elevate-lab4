"""HTTP Server for Production Container Deployment and Healthchecks.

Implements SDD Section 4.1 (Ingress REST API /api/v1/chat) and provides
production container liveness and readiness probes on /healthz.
"""
import json
import logging
import os
import sys
from typing import Any, Optional

logger = logging.getLogger("server")

PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")

try:
    import uvicorn
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    app = FastAPI(
        title="HR Agentic Solution Service",
        description="Production API and Health Gateway for HR Policy Assistant",
        version="1.0.0",
    )

    class ChatRequest(BaseModel):
        query: str
        user_id: Optional[str] = "EMP-1042"
        session_id: Optional[str] = "session-1"

    class ChatResponse(BaseModel):
        response: str
        evidence: list[dict[str, Any]]
        user_id: str
        session_id: str

    @app.get("/healthz")
    @app.get("/health")
    def healthz():
        """Container healthcheck probe returning 200 OK."""
        return {
            "status": "healthy",
            "service": "hr_policy_agent",
            "version": "1.0.0",
        }

    @app.get("/")
    def index():
        return {
            "service": "HR Agentic Solution (MVP 1)",
            "health_check": "/healthz",
            "chat_endpoint": "/api/v1/chat",
        }

    @app.post("/api/v1/chat", response_model=ChatResponse)
    def chat_endpoint(req: ChatRequest):
        if not req.query or not req.query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty.")

        from .agent import run_query_traced

        user_id = req.user_id or "EMP-1042"
        session_id = req.session_id or "session-1"

        answer, evidence = run_query_traced(
            query=req.query,
            user_id=user_id,
            session_id=session_id,
        )

        return ChatResponse(
            response=answer,
            evidence=evidence,
            user_id=user_id,
            session_id=session_id,
        )

    def run_server():
        logger.info("Starting FastAPI/Uvicorn server on %s:%d", HOST, PORT)
        uvicorn.run(app, host=HOST, port=PORT, log_level="info")

except ImportError:
    # Standard library fallback if FastAPI/uvicorn is not available
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class HealthHTTPHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/healthz", "/health"):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {"status": "healthy", "service": "hr_policy_agent", "version": "1.0.0"}
                    ).encode("utf-8")
                )
            elif self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "service": "HR Agentic Solution (MVP 1)",
                            "health_check": "/healthz",
                            "chat_endpoint": "/api/v1/chat",
                        }
                    ).encode("utf-8")
                )
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            if self.path == "/api/v1/chat":
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                query = body.get("query", "")
                user_id = body.get("user_id", "EMP-1042")
                session_id = body.get("session_id", "session-1")

                from .agent import run_query_traced

                answer, evidence = run_query_traced(query, user_id=user_id, session_id=session_id)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(
                    json.dumps(
                        {
                            "response": answer,
                            "evidence": evidence,
                            "user_id": user_id,
                            "session_id": session_id,
                        }
                    ).encode("utf-8")
                )
            else:
                self.send_response(404)
                self.end_headers()

    def run_server():
        logger.info("Starting standard HTTP server on %s:%d", HOST, PORT)
        server = HTTPServer((HOST, PORT), HealthHTTPHandler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()


def main():
    logging.basicConfig(level=logging.INFO)
    run_server()


if __name__ == "__main__":
    main()
