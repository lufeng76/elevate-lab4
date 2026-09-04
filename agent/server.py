"""HTTP Server for Production Container Deployment, Web Chat UI, and Healthchecks.

Implements SDD Section 4.1 (Ingress REST API /api/v1/chat), provides
interactive Web Chat Front-End, mounts ADK Dev UI (/dev-ui/), and provides
production container liveness and readiness probes on /health and /healthz.
"""
import html
import json
import logging
import os
import sys
from typing import Any, Optional

logger = logging.getLogger("server")

PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")

CHAT_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Altostrat HR & IT Policy Assistant</title>
  <link rel="icon" href="/dev-ui/adk_favicon.svg" type="image/svg+xml">
  <style>
    :root {
      --primary: #1a73e8;
      --primary-hover: #1557b0;
      --bg: #f8f9fa;
      --surface: #ffffff;
      --text: #202124;
      --text-secondary: #5f6368;
      --border: #dadce0;
      --user-bubble: #e8f0fe;
      --agent-bubble: #ffffff;
      --code-bg: #f1f3f4;
      --success: #1e8e3e;
      --radius: 12px;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
    body { background-color: var(--bg); color: var(--text); display: flex; flex-direction: column; height: 100vh; }
    header {
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 12px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      box-shadow: 0 1px 2px rgba(60,64,67,0.06);
    }
    .brand { display: flex; align-items: center; gap: 12px; }
    .brand-icon {
      width: 36px; height: 36px; border-radius: 8px; background: var(--primary);
      display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 18px;
    }
    .brand-info h1 { font-size: 16px; font-weight: 600; color: var(--text); }
    .brand-info p { font-size: 12px; color: var(--text-secondary); }
    .header-links { display: flex; align-items: center; gap: 12px; }
    .header-links a {
      font-size: 13px; color: var(--primary); text-decoration: none; font-weight: 500;
      padding: 6px 12px; border-radius: 6px; border: 1px solid var(--border); background: var(--surface);
      transition: background 0.15s, border-color 0.15s;
    }
    .header-links a:hover { background: var(--user-bubble); border-color: var(--primary); }
    .status-badge {
      display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--success);
      background: #e6f4ea; padding: 4px 8px; border-radius: 12px; font-weight: 500;
    }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); }
    .sub-bar {
      background: #e8f0fe; border-bottom: 1px solid #d2e3fc; padding: 8px 24px;
      display: flex; align-items: center; justify-content: space-between; font-size: 13px; color: #174ea6;
    }
    .user-select { display: flex; align-items: center; gap: 8px; }
    .user-select select {
      padding: 4px 8px; border-radius: 4px; border: 1px solid #aecbfa; background: white;
      font-size: 12px; color: #174ea6; font-weight: 500; cursor: pointer;
    }
    .main-container { flex: 1; display: flex; flex-direction: column; max-width: 900px; width: 100%; margin: 0 auto; padding: 16px; overflow: hidden; }
    .chat-window {
      flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 16px;
      padding: 16px 8px; scroll-behavior: smooth;
    }
    .msg-row { display: flex; gap: 12px; max-width: 85%; animation: fadeIn 0.2s ease-in-out; }
    .msg-row.user { align-self: flex-end; flex-direction: row-reverse; }
    .msg-row.agent { align-self: flex-start; }
    .avatar {
      width: 32px; height: 32px; border-radius: 50%; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: bold;
    }
    .msg-row.agent .avatar { background: #e8f0fe; color: var(--primary); border: 1px solid #aecbfa; }
    .msg-row.user .avatar { background: #fce8e6; color: #c5221f; border: 1px solid #fad2cf; }
    .bubble {
      padding: 12px 16px; border-radius: var(--radius); font-size: 14px; line-height: 1.5;
      box-shadow: 0 1px 2px rgba(60,64,67,0.1); word-break: break-word;
    }
    .msg-row.user .bubble { background: var(--primary); color: white; border-bottom-right-radius: 4px; }
    .msg-row.agent .bubble { background: var(--surface); color: var(--text); border: 1px solid var(--border); border-bottom-left-radius: 4px; }
    .bubble p { margin-bottom: 8px; }
    .bubble p:last-child { margin-bottom: 0; }
    .bubble ul, .bubble ol { margin-left: 20px; margin-bottom: 8px; }
    .bubble li { margin-bottom: 4px; }
    .evidence-box {
      margin-top: 10px; padding: 8px 12px; background: var(--code-bg); border-radius: 8px;
      font-size: 12px; border: 1px solid var(--border);
    }
    .evidence-header { font-weight: 600; color: var(--text-secondary); margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }
    .evidence-item { margin-top: 4px; padding: 4px 0; border-top: 1px dashed var(--border); color: #3c4043; }
    .evidence-item strong { color: var(--primary); }
    .chips-container { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; padding: 0 4px; }
    .chip {
      background: var(--surface); border: 1px solid var(--border); border-radius: 16px;
      padding: 6px 14px; font-size: 12px; color: var(--text-secondary); cursor: pointer;
      transition: all 0.15s;
    }
    .chip:hover { background: var(--user-bubble); color: var(--primary); border-color: var(--primary); }
    .input-area {
      background: var(--surface); border: 1px solid var(--border); border-radius: 24px;
      padding: 4px 8px 4px 16px; display: flex; align-items: center; gap: 8px;
      box-shadow: 0 2px 6px rgba(60,64,67,0.1);
    }
    .input-area:focus-within { border-color: var(--primary); box-shadow: 0 2px 8px rgba(26,115,232,0.25); }
    textarea {
      flex: 1; border: none; outline: none; resize: none; font-size: 14px; height: 24px;
      max-height: 120px; line-height: 24px; background: transparent; color: var(--text);
    }
    .send-btn {
      width: 36px; height: 36px; border-radius: 50%; background: var(--primary);
      border: none; color: white; display: flex; align-items: center; justify-content: center;
      cursor: pointer; transition: background 0.15s; flex-shrink: 0;
    }
    .send-btn:hover { background: var(--primary-hover); }
    .send-btn:disabled { background: var(--border); cursor: not-allowed; }
    .typing { display: none; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary); padding: 4px 8px; }
    .typing-dots { display: flex; gap: 4px; }
    .typing-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--primary); animation: blink 1.2s infinite ease-in-out; }
    .typing-dot:nth-child(2) { animation-delay: 0.2s; }
    .typing-dot:nth-child(3) { animation-delay: 0.4s; }
    @keyframes blink { 0%, 80%, 100% { opacity: 0.2; transform: scale(0.8); } 40% { opacity: 1; transform: scale(1.1); } }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
  </style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="brand-icon">HR</div>
      <div class="brand-info">
        <h1>Altostrat HR & IT Policy Assistant</h1>
        <p>Enterprise Grounded Agentic AI (ADK 2.4 / Gemini 3.5 Flash)</p>
      </div>
    </div>
    <div class="header-links">
      <span class="status-badge"><span class="status-dot"></span> Online</span>
      <a href="/dev-ui/" target="_blank" title="Open Google ADK Developer Playground">ADK Dev UI ↗</a>
      <a href="/docs" target="_blank" title="Interactive Swagger REST API Documentation">API Docs ↗</a>
      <a href="/health" target="_blank" title="Container Health Probe">/health ↗</a>
    </div>
  </header>

  <div class="sub-bar">
    <div class="user-select">
      <span>Caller Identity (OBO):</span>
      <select id="userSelect" onchange="switchUser()">
        <option value="EMP-1042">EMP-1042 (Sarah Jenkins — Singapore / Engineering)</option>
        <option value="EMP-2091">EMP-2091 (Alex Rivera — Product Design)</option>
        <option value="EMP-3104">EMP-3104 (Priya Sharma — Global Ops)</option>
      </select>
    </div>
    <div>
      <span id="sessionDisplay" style="margin-right: 12px;">Session: <strong id="sessionId">session-1</strong></span>
      <button onclick="newChat()" style="background:none; border:none; color:#174ea6; text-decoration:underline; cursor:pointer; font-size:12px;">New Chat</button>
    </div>
  </div>

  <div class="main-container">
    <div class="chat-window" id="chatWindow">
      <div class="msg-row agent">
        <div class="avatar">AI</div>
        <div class="bubble">
          <p><strong>Welcome to Altostrat HR & IT Assistant.</strong></p>
          <p>I am your verified enterprise policy advisor. I can answer questions about company policies, check leave eligibility, verify conduct guidelines, submit sick leave, or assist with IT hardware procurement.</p>
          <p>How may I assist you today?</p>
        </div>
      </div>
    </div>

    <div class="chips-container" id="chipsContainer">
      <div class="chip" onclick="sendPrompt('What is the bereavement leave policy?')">What is the bereavement leave policy?</div>
      <div class="chip" onclick="sendPrompt('Can I take bereavement leave for a pet?')">Can I take bereavement leave for a pet?</div>
      <div class="chip" onclick="sendPrompt('How much annual vacation leave do I get in Singapore?')">Singapore vacation allowance?</div>
      <div class="chip" onclick="sendPrompt('Can I accept a $150 dinner invitation from a commercial vendor?')">Vendor dinner acceptance rules?</div>
      <div class="chip" onclick="sendPrompt('How do I request emergency medical leave?')">Emergency medical leave request?</div>
    </div>

    <div class="typing" id="typingIndicator">
      <div class="typing-dots">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
      <span>Consulting enterprise knowledge bundle & verifying grounding...</span>
    </div>

    <div class="input-area">
      <textarea id="queryInput" rows="1" placeholder="Ask a policy or transaction question... (Press Enter to send)" onkeydown="handleKeyDown(event)"></textarea>
      <button class="send-btn" id="sendBtn" onclick="submitMessage()" title="Send message">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
          <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
        </svg>
      </button>
    </div>
  </div>

  <script>
    let currentUserId = document.getElementById('userSelect').value;
    let currentSessionId = 'session-' + Date.now().toString().slice(-4);
    document.getElementById('sessionId').innerText = currentSessionId;

    function switchUser() {
      currentUserId = document.getElementById('userSelect').value;
      newChat();
    }

    function newChat() {
      currentSessionId = 'session-' + Date.now().toString().slice(-4);
      document.getElementById('sessionId').innerText = currentSessionId;
      const chatWindow = document.getElementById('chatWindow');
      chatWindow.innerHTML = `
        <div class="msg-row agent">
          <div class="avatar">AI</div>
          <div class="bubble">
            <p><strong>Session reset.</strong> Active user: <code>${currentUserId}</code>.</p>
            <p>How may I assist you with Altostrat policies or self-service transactions?</p>
          </div>
        </div>
      `;
    }

    function handleKeyDown(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitMessage();
      }
    }

    function sendPrompt(text) {
      document.getElementById('queryInput').value = text;
      submitMessage();
    }

    function formatMarkdown(text) {
      if (!text) return '';
      let escaped = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');

      // Bold **text**
      escaped = escaped.replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
      // Italic *text*
      escaped = escaped.replace(/\\*(.*?)\\*/g, '<em>$1</em>');
      // Inline code `code`
      escaped = escaped.replace(/`([^`]+)`/g, '<code style="background:#f1f3f4;padding:2px 4px;border-radius:4px;">$1</code>');

      // Paragraphs & lines
      const lines = escaped.split('\\n');
      let out = '';
      let inList = false;

      for (let line of lines) {
        line = line.trim();
        if (line.startsWith('- ') || line.startsWith('* ')) {
          if (!inList) { out += '<ul>'; inList = true; }
          out += `<li>${line.substring(2)}</li>`;
        } else if (line.match(/^\\d+\\.\\s/)) {
          if (!inList) { out += '<ol>'; inList = true; }
          out += `<li>${line.replace(/^\\d+\\.\\s/, '')}</li>`;
        } else {
          if (inList) { out += '</ul>'; inList = false; }
          if (line) {
            if (line.startsWith('# ')) out += `<h3>${line.substring(2)}</h3>`;
            else if (line.startsWith('## ')) out += `<h4>${line.substring(3)}</h4>`;
            else if (line.startsWith('### ')) out += `<h5>${line.substring(4)}</h5>`;
            else out += `<p>${line}</p>`;
          }
        }
      }
      if (inList) out += '</ul>';
      return out;
    }

    async function submitMessage() {
      const input = document.getElementById('queryInput');
      const query = input.value.trim();
      if (!query) return;

      const chatWindow = document.getElementById('chatWindow');
      const typing = document.getElementById('typingIndicator');
      const sendBtn = document.getElementById('sendBtn');

      // Append User message
      const userRow = document.createElement('div');
      userRow.className = 'msg-row user';
      userRow.innerHTML = `
        <div class="avatar">You</div>
        <div class="bubble"><p>${query.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p></div>
      `;
      chatWindow.appendChild(userRow);
      input.value = '';
      chatWindow.scrollTop = chatWindow.scrollHeight;

      // Show typing indicator
      typing.style.display = 'flex';
      sendBtn.disabled = true;

      try {
        const response = await fetch('/api/v1/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query: query,
            user_id: currentUserId,
            session_id: currentSessionId
          })
        });

        const data = await response.json();
        typing.style.display = 'none';
        sendBtn.disabled = false;

        const agentRow = document.createElement('div');
        agentRow.className = 'msg-row agent';

        let evidenceHtml = '';
        if (data.evidence && data.evidence.length > 0) {
          const items = data.evidence.map(e => {
            const title = e.payload?.title || e.payload?.resource || e.tool || 'Policy Document';
            const resource = e.payload?.resource ? `<br><small style="color:#5f6368">${e.payload.resource}</small>` : '';
            return `<div class="evidence-item"><strong>${title}</strong>${resource}</div>`;
          }).join('');
          evidenceHtml = `
            <details class="evidence-box">
              <summary class="evidence-header">📚 Grounded Policy Sources (${data.evidence.length} cited)</summary>
              ${items}
            </details>
          `;
        }

        agentRow.innerHTML = `
          <div class="avatar">AI</div>
          <div class="bubble">
            ${formatMarkdown(data.response || 'No response returned.')}
            ${evidenceHtml}
          </div>
        `;
        chatWindow.appendChild(agentRow);
        chatWindow.scrollTop = chatWindow.scrollHeight;

      } catch (err) {
        typing.style.display = 'none';
        sendBtn.disabled = false;
        const errRow = document.createElement('div');
        errRow.className = 'msg-row agent';
        errRow.innerHTML = `
          <div class="avatar" style="background:#fce8e6; color:#c5221f;">!</div>
          <div class="bubble" style="border-color:#fad2cf; background:#fffbfa;">
            <p style="color:#c5221f;"><strong>Error connecting to agent service:</strong> ${err.message}</p>
          </div>
        `;
        chatWindow.appendChild(errRow);
        chatWindow.scrollTop = chatWindow.scrollHeight;
      }
    }
  </script>
</body>
</html>
"""

try:
    import uvicorn
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from pydantic import BaseModel

    try:
        from google.adk.cli.fast_api import get_fast_api_app
        # Initialize the official ADK web application (with /dev-ui/ and ADK endpoints)
        app = get_fast_api_app(agents_dir=".", web=True)
        # Remove existing default root handler so we can serve the custom Chat UI and handle content negotiation
        app.router.routes = [
            r for r in app.router.routes
            if getattr(r, "path", None) not in ("/", "/healthz", "/health")
        ]
    except Exception as exc:
        logger.warning("Could not initialize ADK DevServer (%s); initializing base FastAPI", exc)
        app = FastAPI(
            title="HR Agentic Solution Service",
            description="Production API, Web Chat Front-End, and Health Gateway",
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

    @app.get("/", response_class=HTMLResponse)
    def root_endpoint(request: Request):
        """Serves interactive Chat Front-End for browsers, or API metadata for JSON clients."""
        accept = request.headers.get("accept", "")
        if "application/json" in accept and "text/html" not in accept:
            return JSONResponse({
                "service": "HR Agentic Solution (MVP 1)",
                "health_check": "/healthz",
                "chat_endpoint": "/api/v1/chat",
                "web_chat": "/",
                "dev_ui": "/dev-ui/",
            })
        return HTMLResponse(content=CHAT_HTML, status_code=200)

    @app.get("/chat", response_class=HTMLResponse)
    def chat_ui():
        """Dedicated route for Web Chat Front-End."""
        return HTMLResponse(content=CHAT_HTML, status_code=200)

    @app.post("/api/v1/chat", response_model=ChatResponse)
    def chat_endpoint(req: ChatRequest):
        """Ingress REST API satisfying SDD Section 4.1."""
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
            elif self.path in ("/", "/chat"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(CHAT_HTML.encode("utf-8"))
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
