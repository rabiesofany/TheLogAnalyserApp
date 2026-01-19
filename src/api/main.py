"""FastAPI application for error classification."""

import json
import os
from typing import List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from dotenv import load_dotenv

from src.models import (
    ClassificationRequest,
    ClassificationResponse,
    ErrorClassification,
    ErrorInsight,
    ErrorLog,
    Severity,
    Complexity,
    Stage
)
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

        function formatStageLine(error) {
          const stageLabel = stageDisplayValue(error.stage);
          const lineLabel = withFallback(error.line_number, "N/A");
          const messageSnippet = buildSnippet(error);
          const detail = messageSnippet ? ` (${messageSnippet})` : "";
          return `${stageLabel} at line ${lineLabel}${detail}`;
        }

        function buildSnippet(error) {
          const parts = [];
          if (error.message) {
            parts.push(error.message.trim());
          }
          if (error.context && error.context.length) {
            parts.push(error.context.join(" | ").trim());
          }
          const combined = parts.filter(Boolean).join(" | ");
          return combined.slice(0, 160);
        }

        function formatSeverityLabel(value) {
          return withFallback(value, "unknown");
        }

        function formatComplexityLabel(value) {
          return withFallback(value, "unknown");
        }

        function formatInsightLine(insight) {
          const stageLabel = stageDisplayValue(insight.stage);
          const severityLabel = withFallback(insight.severity, "unknown");
          const complexityLabel = withFallback(insight.complexity, "unknown");
          const lineLabel = withFallback(insight.line_number, "N/A");
          const snippet = insight.snippet ? ` (${insight.snippet})` : "";
          return `${stageLabel} [${severityLabel}, ${complexityLabel}] at line ${lineLabel}${snippet}`;
        }

        function buildStageDetails(insights) {
          if (!insights || insights.length === 0) {
            return "<p>No parsed errors available.</p>";
          }
          return insights.map((insight, idx) => `
            <p style="margin:0.1rem 0;"><strong>${idx + 1}.</strong> ${formatInsightLine(insight)}</p>
          `).join("");
        }
        function withFallback(value, placeholder) {
          return value != null ? value : placeholder;
        }

        function stopTimer() {
          if (timerId) {
            clearInterval(timerId);
            timerId = null;
          }
        }

        function createSections() {
          const classificationContainer = document.createElement("div");
          classificationContainer.className = "card";
          const parsedErrorsContainer = document.createElement("div");
          parsedErrorsContainer.className = "card";

          classificationContainer.innerHTML = "<h2>Classification progress...</h2>";
          parsedErrorsContainer.innerHTML = `
            <h2>Parsed Errors</h2>
            <div class="errors-list"></div>
          `;

          return { classificationContainer, parsedErrorsContainer };
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

        function handleSuggestionToggle(event) {
          const button = event.target.closest(".toggle-suggestions");
          if (!button) {
            return;
          }
          const targetId = button.dataset.target;
          const section = document.getElementById(targetId);
          if (!section) {
            return;
          }
          const isOpen = section.style.display === "block";
          section.style.display = isOpen ? "none" : "block";
          button.textContent = isOpen ? "Show Fix Suggestions" : "Hide Fix Suggestions";
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
              <div class="stage-details" style="margin-top:0.75rem;">
                <h3 style="margin:0 0 0.25rem;">Detected stages</h3>
                ${buildStageDetails(payload.error_insights)}
              </div>
            `;
            stopTimer();
            statusEl.textContent = "Classification received.";
          } else if (type === "suggestion") {
            const { index, total, suggestion, error_index, error_total } = payload;
            const targetIndex = error_index ?? 0;
            const suggestionsSection = containers.parsedErrorsContainer.querySelector(`.error-suggestions[data-error-index="${targetIndex}"]`);
            if (!suggestionsSection) {
              return;
            }
            const list = suggestionsSection.querySelector(".suggestion-list");
            if (!list) {
              return;
            }
            const placeholder = document.getElementById(`suggestionPlaceholder-${targetIndex}`);
            if (placeholder) {
              placeholder.remove();
            }

            const card = document.createElement("div");
            card.className = "card";
            card.style.padding = "0.75rem";
            card.style.marginBottom = "0.5rem";
            const ordinal = list.childElementCount + 1;
            card.innerHTML = `
              <h3 style="margin:0;"><strong>${ordinal}. ${suggestion.title}</strong></h3>
              <p><strong>Confidence:</strong> ${(suggestion.confidence * 100).toFixed(1)}%</p>
              <p><strong>Why it happened:</strong> <span id="suggestion-${index}-root"></span></p>
              <p><strong>Details:</strong> <span id="suggestion-${index}-description"></span></p>
              <p><strong>Code Before:</strong> <span id="suggestion-${index}-code_before"></span></p>
              <p><strong>Code After:</strong> <span id="suggestion-${index}-code_after"></span></p>
            `;

            const setFallbackText = (id, value, fallback) => {
              const el = card.querySelector(`#${id}`);
              if (el && (value === undefined || value === null || value === "")) {
                el.textContent = fallback;
              }
            };

            setFallbackText(`suggestion-${index}-root`, suggestion.root_cause, "No root cause provided.");
            setFallbackText(`suggestion-${index}-description`, suggestion.description, "Details coming via stream...");
            setFallbackText(`suggestion-${index}-code_before`, suggestion.code_before, "N/A");
            setFallbackText(`suggestion-${index}-code_after`, suggestion.code_after, "N/A");

            list.appendChild(card);
            const header = suggestionsSection.querySelector("h4");
            if (header) {
              header.textContent = `Fix Suggestions (${list.childElementCount}/${error_total || list.childElementCount})`;
            }
          } else if (type === "parsed_errors") {
            const list = containers.parsedErrorsContainer.querySelector(".errors-list");
            if (!list) {
              return;
            }
          list.innerHTML = payload.map((error, idx) => `
              <div class="card error-card" style="padding:0.75rem;margin-bottom:0.5rem;">
                <h3 style="margin:0;"><strong>Error ${idx + 1}</strong></h3>
                <p><strong>Type:</strong> ${error.error_type}</p>
                <p><strong>Severity:</strong> ${formatSeverityLabel(error.severity)}</p>
                <p><strong>Stage:</strong> ${formatStageLine(error)}</p>
                <p><strong>Complexity:</strong> ${formatComplexityLabel(error.complexity)}</p>
                <p><strong>File:</strong> ${withFallback(error.file_path, "N/A")}</p>
                <button class="toggle-suggestions" type="button" data-target="suggestions-${idx}" style="margin-top:0.5rem;">Show Fix Suggestions</button>
                <div class="error-suggestions" id="suggestions-${idx}" data-error-index="${idx}" style="display:none;margin-top:0.75rem;">
                  <h4 style="margin:0 0 0.25rem;">Fix Suggestions</h4>
                  <div class="suggestion-list"></div>
                  <p id="suggestionPlaceholder-${idx}" style="color:#6b7280;margin:0;">Awaiting suggestions...</p>
                </div>
              </div>
            `).join("");
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
          resultEl.appendChild(containers.parsedErrorsContainer);
          containers.parsedErrorsContainer.addEventListener("click", handleSuggestionToggle);

          stopTimer();
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
        error_insights = _generate_error_insights(error_log, classification)

        # Step 3: Generate fix suggestions
        suggestions = generate_fix_suggestions(
            error_log,
            classification
        )

        # Step 4: Build response
        response = ClassificationResponse(
            classification=classification,
            suggestions=suggestions,
            parsed_errors=error_log.errors,
            error_insights=error_insights
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
    if not text:
        return
    for word in text.split():
        yield _serialize_event("word", {"target": target_id, "text": word})


def _generate_error_insights(error_log: ErrorLog, classification: ErrorClassification) -> List[ErrorInsight]:
    insights: List[ErrorInsight] = []
    for error in error_log.errors:
        severity = error.severity
        complexity = error.complexity if error.complexity is not None else classification.complexity
        snippet_parts = [error.message or ""]
        if error.context:
            snippet_parts.append(" | ".join(error.context))
        snippet = " ".join(part.strip() for part in snippet_parts if part).strip()
        if len(snippet) > 220:
            snippet = snippet[:217] + "..."
        insights.append(ErrorInsight(
            stage=error.stage,
            severity=severity,
            complexity=complexity,
            line_number=error.line_number,
            file_path=error.file_path,
            snippet=snippet or None
        ))
    return insights


def _event_stream(error_log):
    try:
        classification = classify_error_log(error_log)
        classification_payload = classification.dict()
        classification_payload["errors"] = [e.dict() for e in error_log.errors]
        error_insights = _generate_error_insights(error_log, classification)
        classification_payload["error_insights"] = [insight.dict() for insight in error_insights]
        yield _serialize_event("classification", classification_payload)
        yield _serialize_event("parsed_errors", [e.dict() for e in error_log.errors])
        yield from _stream_words("classificationReasoning", classification.reasoning)

        suggestions = generate_fix_suggestions(error_log, classification)
        total_suggestions = len(suggestions)
        error_totals = {}
        for suggestion in suggestions:
            idx = suggestion.error_index if suggestion.error_index is not None else 0
            error_totals[idx] = error_totals.get(idx, 0) + 1
        for idx, suggestion in enumerate(suggestions):
            error_index = suggestion.error_index
            if error_index is None:
                error_index = min(idx, len(error_insights) - 1 if error_insights else 0)
            yield _serialize_event("suggestion", {
                "index": idx,
                "total": total_suggestions,
                "suggestion": suggestion.dict(),
                "error_index": error_index,
                "error_total": error_totals.get(error_index, 1)
            })
            yield from _stream_words(f"suggestion-{idx}-description", suggestion.description)
            yield from _stream_words(f"suggestion-{idx}-root", suggestion.root_cause)
            if suggestion.code_before:
                yield from _stream_words(f"suggestion-{idx}-code_before", suggestion.code_before)
            if suggestion.code_after:
                yield from _stream_words(f"suggestion-{idx}-code_after", suggestion.code_after)

        # parsed_errors already emitted before suggestions
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
