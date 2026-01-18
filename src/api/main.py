"""FastAPI application for error classification."""

import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from dotenv import load_dotenv

from src.models import ClassificationRequest, ClassificationResponse
from src.parser.error_parser import parse_error_log
from src.classifier.error_classifier import classify_error_log
from src.fix_suggester.fix_suggester import generate_fix_suggestions

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="PLC Error Classification API",
    description="AI-powered classification and fix suggestions for PLC compilation errors",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "PLC Error Classification API",
        "version": "1.0.0",
        "endpoints": {
            "classify": "POST /classify - Classify error logs and get fix suggestions",
            "playground": "GET /playground - Paste errors via the browser and inspect the JSON response"
        }
    }


@app.get("/playground", response_class=HTMLResponse)
async def playground():
    """Simple UI to paste error logs and view classification output."""
    ui_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <title>PLC Error Classification Playground</title>
      <style>
        body { font-family: system-ui, sans-serif; margin: 2rem; background: #ffffff; color: #0f172a; }
        textarea { width: 100%; height: 220px; font-family: Menlo, monospace; font-size: 0.95rem; margin-bottom: 0.75rem; }
        button { padding: 0.7rem 1.4rem; font-size: 1rem; cursor: pointer; }
        .card { background: #ffffff; padding: 1rem; margin-bottom: 1rem; border-radius: 10px; box-shadow: 0 4px 18px rgba(0,0,0,0.08); color: #0f172a; }
        .card h2, .card h3 { color: #0f172a; }
        pre {
          background: #f3f4f6;
          color: #0f172a;
          padding: 1rem;
          border-radius: 6px;
          white-space: pre-wrap;
          font-family: Menlo, monospace;
        }
      </style>
    </head>
    <body>
      <h1>PLC Error Classification Playground</h1>
      <p>Paste a PLC error log below and click <strong>Classify</strong>.</p>
      <textarea id="logInput" placeholder="Paste error log text here..."></textarea>
      <br />
      <button onclick="runClassification()">Classify</button>
      <div id="status" class="card" style="display:none;"></div>
      <div id="result" class="card" style="display:none;"></div>
      <div class="card">
        <strong>Total submit attempts:</strong> <span id="submitCount">0</span><br />
        <strong>Pending responses:</strong> <span id="pendingCount">0</span><br />
        <strong>Time elapsed:</strong> <span id="timerDisplay">00</span> s
      </div>
      <script>
        let submitCount = 0;
        let pendingCount = 0;
        let timerSeconds = 0;
        let timerId = null;

        function formatTimer(seconds) {
          return seconds.toString().padStart(2, "0");
        }

        function updateCounters() {
          document.getElementById("submitCount").textContent = submitCount;
          document.getElementById("pendingCount").textContent = pendingCount;
          document.getElementById("timerDisplay").textContent = formatTimer(timerSeconds);
        }

        function stageDisplayValue(stage) {
          if (stage && stage.value !== undefined && stage.value !== null) {
            return stage.value;
          }
          return stage;
        }

        function withFallback(value, placeholder) {
          return value != null ? value : placeholder;
        }

        function createSections() {
          const classificationContainer = document.createElement("div");
          classificationContainer.className = "card";
          const suggestionsContainer = document.createElement("div");
          suggestionsContainer.className = "card";
          const parsedErrorsContainer = document.createElement("div");
          parsedErrorsContainer.className = "card";

          classificationContainer.innerHTML = "<h2>Classification progress...</h2>";
          suggestionsContainer.innerHTML = "<h2>Fix Suggestions</h2>";
          parsedErrorsContainer.innerHTML = "<h2>Parsed Errors</h2>";

          return { classificationContainer, suggestionsContainer, parsedErrorsContainer };
        }

        function appendWord(targetId, word) {
          const target = document.getElementById(targetId);
          if (!target) {
            return;
          }
          if (target.textContent) {
            target.textContent += " " + word;
          } else {
            target.textContent = word;
          }
        }

        function handleStreamEvent(event, containers, statusEl) {
          const { type, payload } = event;

          if (type === "classification") {
            containers.classificationContainer.innerHTML = `
              <h2>Classification</h2>
              <p><strong>Severity:</strong> ${payload.severity}</p>
              <p><strong>Stage:</strong> ${payload.stage}</p>
              <p><strong>Complexity:</strong> ${payload.complexity}</p>
              <p><strong>Reasoning:</strong> <span id="classificationReasoning"></span></p>
            `;
          } else if (type === "suggestions") {
            const rows = payload.map((suggestion, idx) => `
              <div class="card" style="padding:0.75rem;margin-bottom:0.5rem;">
                <h3 style="margin:0;"><strong>${idx + 1}. ${suggestion.title}</strong></h3>
                <p><strong>Confidence:</strong> ${(suggestion.confidence * 100).toFixed(1)}%</p>
                <p><strong>Root Cause:</strong> <span id="suggestion-${idx}-root"></span></p>
                <p><strong>Description:</strong> <span id="suggestion-${idx}-description"></span></p>
                <p><strong>Code Before:</strong> <span id="suggestion-${idx}-code_before"></span></p>
                <p><strong>Code After:</strong> <span id="suggestion-${idx}-code_after"></span></p>
              </div>
            `).join("");

            containers.suggestionsContainer.innerHTML = `
              <h2>Fix Suggestions (${payload.length})</h2>
              ${rows || "<p>No suggestions returned.</p>"}
            `;
          } else if (type === "parsed_errors") {
            containers.parsedErrorsContainer.innerHTML = `
              <h2>Parsed Errors (${payload.length})</h2>
              ${payload.map((error, idx) => `
                <div class="card" style="padding:0.75rem;margin-bottom:0.5rem;">
                  <h3 style="margin:0;"><strong>Error ${idx + 1}</strong></h3>
                  <p><strong>Type:</strong> ${error.error_type}</p>
                  <p><strong>Stage:</strong> ${stageDisplayValue(error.stage)}</p>
                  <p><strong>Message:</strong> ${error.message}</p>
                  <p><strong>Line:</strong> ${withFallback(error.line_number, "N/A")}</p>
                  <p><strong>File:</strong> ${withFallback(error.file_path, "N/A")}</p>
                </div>
              `).join("")}
            `;
          } else if (type === "complete") {
            statusEl.textContent = "Classification stream complete.";
          } else if (type === "error") {
            statusEl.textContent = `Stream error: ${payload.detail}`;
          } else if (type === "word") {
            appendWord(payload.target, payload.text);
          }
        }

        async function runClassification() {
          const log = document.getElementById("logInput").value.trim();
          if (!log) {
            alert("Paste an error log first.");
            return;
          }

          const statusEl = document.getElementById("status");
          const resultEl = document.getElementById("result");
          submitCount += 1;
          pendingCount += 1;
          updateCounters();
          statusEl.style.display = "block";
          statusEl.textContent = `Streaming classification (attempt ${submitCount})...`;
          resultEl.style.display = "block";
          resultEl.innerHTML = "";

          const containers = createSections();
          resultEl.appendChild(containers.classificationContainer);
          resultEl.appendChild(containers.suggestionsContainer);
          resultEl.appendChild(containers.parsedErrorsContainer);

          if (timerId) {
            clearInterval(timerId);
          }
          timerSeconds = 0;
          updateCounters();
          timerId = setInterval(() => {
            timerSeconds += 1;
            updateCounters();
          }, 1000);

          try {
            const response = await fetch("/classify/stream", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ error_log: log })
            });

            if (!response.ok) {
              const errorBody = await response.json().catch(() => ({}));
              throw new Error(errorBody.detail || "Failed to classify error log.");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            const newlinePair = String.fromCharCode(10, 10);

            while (true) {
              const { done, value } = await reader.read();
              if (done) {
                break;
              }
              buffer += decoder.decode(value, { stream: true });
              const events = buffer.split(newlinePair);
              buffer = events.pop();

              for (const chunk of events) {
                if (!chunk.trim()) {
                  continue;
                }
                const line = chunk.trim();
                if (!line.startsWith("data:")) {
                  continue;
                }
                const payload = JSON.parse(line.slice(5));
                handleStreamEvent(payload, containers, statusEl);
              }
            }
          } catch (error) {
            statusEl.textContent = `Error: ${error.message}`;
          } finally {
            pendingCount = Math.max(0, pendingCount - 1);
            if (timerId) {
              clearInterval(timerId);
              timerId = null;
            }
            updateCounters();
          }
        }
      </script>
    </body>
    </html>
    """

    return HTMLResponse(ui_html)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/classify", response_model=ClassificationResponse)
async def classify_error(request: ClassificationRequest):
    """Classify an error log and provide fix suggestions.

    Args:
        request: Classification request with error log

    Returns:
        Classification response with severity, stage, complexity, and fix suggestions

    Raises:
        HTTPException: If classification fails
    """
    try:
        # Step 1: Parse the error log
        error_log = parse_error_log(request.error_log)

        if not error_log.errors:
            raise HTTPException(
                status_code=400,
                detail="No errors found in log. Please check the log format."
            )

        # Step 2: Classify the errors
        classification = classify_error_log(error_log)

        # Step 3: Generate fix suggestions
        suggestions = generate_fix_suggestions(
            error_log,
            classification
        )

        # Step 4: Build response
        response = ClassificationResponse(
            classification=classification,
            suggestions=suggestions,
            parsed_errors=error_log.errors
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}"
        )


def _serialize_event(event_type: str, payload):
    """Format a Server-Sent Events chunk."""
    return f"data: {json.dumps({'type': event_type, 'payload': payload})}\n\n"


def _stream_words(target_id: str, text: str):
    for word in text.split():
        yield _serialize_event("word", {"target": target_id, "text": word})


def _event_stream(error_log):
    try:
        classification = classify_error_log(error_log)
        yield _serialize_event("classification", classification.dict())
        yield from _stream_words("classificationReasoning", classification.reasoning)

        suggestions = generate_fix_suggestions(error_log, classification)
        yield _serialize_event("suggestions", [s.dict() for s in suggestions])
        for idx, suggestion in enumerate(suggestions):
            yield from _stream_words(f"suggestion-{idx}-description", suggestion.description)
            yield from _stream_words(f"suggestion-{idx}-root", suggestion.root_cause)
            if suggestion.code_before:
                yield from _stream_words(f"suggestion-{idx}-code_before", suggestion.code_before)
            if suggestion.code_after:
                yield from _stream_words(f"suggestion-{idx}-code_after", suggestion.code_after)

        yield _serialize_event("parsed_errors", [e.dict() for e in error_log.errors])
        yield _serialize_event("complete", {"status": "ok"})
    except Exception as exc:
        yield _serialize_event("error", {"detail": str(exc)})


@app.post("/classify/stream")
async def classify_error_stream(request: ClassificationRequest):
    """Stream classification progress back to the client."""
    try:
        error_log = parse_error_log(request.error_log)

        if not error_log.errors:
            raise HTTPException(
                status_code=400,
                detail="No errors found in log. Please check the log format."
            )

        return StreamingResponse(_event_stream(error_log), media_type="text/event-stream")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Classification failed: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    uvicorn.run(app, host=host, port=port)
