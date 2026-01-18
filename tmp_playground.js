
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

            while (true) {
              const { done, value } = await reader.read();
              if (done) {
                break;
              }
              buffer += decoder.decode(value, { stream: true });
              const events = buffer.split("\n\n");
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
      