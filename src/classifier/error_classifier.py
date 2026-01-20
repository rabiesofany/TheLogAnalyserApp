"""Error classifier using Anthropic."""

import json
import os
from typing import Optional
from anthropic import Anthropic

from src.models import (
    ErrorLog,
    ErrorClassification,
    Severity,
    Stage,
    Complexity
)


class ErrorClassifier:
    """Classifies PLC compilation errors using OpenAI."""

    def __init__(self, model: Optional[str] = None):
        """Initialize the classifier with Anthropic."""
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model or "claude-haiku-4-5-20251001"

    def classify(self, error_log: ErrorLog) -> ErrorClassification:
        """Classify an error log.

        Args:
            error_log: Parsed error log

        Returns:
            ErrorClassification with severity, stage, and complexity
        """
        prompt = self._build_classification_prompt(error_log)
        response = self._call_anthropic(prompt)

        return self._parse_classification_response(response)

    def _build_classification_prompt(self, error_log: ErrorLog) -> str:
        """Build the classification prompt."""
        errors_summary = "\n".join([
            f"- {e.error_type} at {e.stage.value}: {e.message[:100]}"
            for e in error_log.errors
        ])

        prompt = f"""You are an expert PLC (Programmable Logic Controller) and industrial automation engineer.

Analyze the following PLC build / compilation log and classify the PRIMARY / ROOT error.
This task is classification ONLY. Do NOT suggest fixes.

––––––––––––––––––––
CLASSIFICATION AXES
––––––––––––––––––––

Severity:
- blocking: The build or execution cannot proceed (e.g., compiler errors, “bailing out”, non-zero exit codes, unhandled exceptions).
- warning: The pipeline continues past this issue, but it is risky or non-compliant.
- info: Informational only.

SEVERITY RULES (STRICT):
- Infer severity from pipeline behavior, NOT message wording.
- Any unhandled exception or Python traceback is ALWAYS blocking.
- A message labeled “Warning” is blocking if the build stops afterward.
- If severity is BLOCKING at the summary level, at least one detected failure MUST justify blocking.

––––––––––––––––––––

Stage (choose ONLY ONE primary stage):
- xml_validation: PLCopen / XML schema validation errors.
- code_generation: IEC/ST code generation failures before IEC compilation.
- iec_compilation: IEC/ST semantic or compilation errors (e.g., CONST assignment, type rules).
- c_compilation: Native C compiler errors.
- unknown: Only if the stage cannot be determined from the log.

STAGE RULES (STRICT):
- Select the stage where the build ACTUALLY FAILS.
- Do NOT select downstream “failed” or umbrella messages that are consequences of an earlier error.
- If multiple issues exist, choose the stage of the ROOT cause.

––––––––––––––––––––

Fix Complexity:
- trivial: Well-known, common PLC fixes (schema re-export, CONST misuse, syntax/semantic rules).
- moderate: Requires understanding of tool internals or data flow (null propagation, generator validation).
- complex: Architectural redesign, multi-component refactor, or multiple independent root causes.

COMPLEXITY RULES (STRICT):
- DEFAULT to trivial unless there is explicit evidence otherwise.
- XML schema / XSD violations are TRIVIAL by default.
- Cascading errors alone do NOT increase complexity.
- “Complex” requires clear proof of architectural or multi-module change.

––––––––––––––––––––
ERROR TYPE AWARENESS (MENTAL MODEL)
––––––––––––––––––––

Use this mapping when reasoning (do NOT output this field):
- XML schema violations → Syntax / Schema validation errors
- IEC semantic rule violations → Logic errors
- Tool crashes / tracebacks → Runtime errors

––––––––––––––––––––
CASCADING ERRORS
––––––––––––––––––––

Cascading Errors Flag: {error_log.has_cascading_errors}

RULES:
- Identify the PRIMARY / ROOT error only.
- Do NOT classify consequence or umbrella errors (e.g., “PLC code generation failed!”).
- Secondary warnings may be acknowledged in reasoning but must NOT override root classification.

––––––––––––––––––––
INPUT
––––––––––––––––––––

Error Log Summary:
{errors_summary}

Full Error Log (truncated):
{error_log.raw_log[:2000]}

––––––––––––––––––––
OUTPUT FORMAT (STRICT)
––––––––––––––––––––

Respond ONLY with a JSON object in EXACTLY this format:

{{
  "severity": "blocking|warning|info",
  "stage": "xml_validation|code_generation|iec_compilation|c_compilation|unknown",
  "complexity": "trivial|moderate|complex",
  "reasoning": "Concise explanation anchored to concrete log evidence (error messages, stack trace lines, or compiler output)."
}}"""

        return prompt

    def _call_anthropic(self, prompt: str) -> str:
        """Call OpenAI API."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def _parse_classification_response(self, response: str) -> ErrorClassification:
        """Parse LLM response into ErrorClassification."""
        try:
            # Extract JSON from response (handle markdown code blocks)
            if "```json" in response:
                json_start = response.find("```json") + 7
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()
            elif "```" in response:
                json_start = response.find("```") + 3
                json_end = response.find("```", json_start)
                response = response[json_start:json_end].strip()

            data = json.loads(response)

            return ErrorClassification(
                severity=Severity(data["severity"]),
                stage=Stage(data["stage"]),
                complexity=Complexity(data["complexity"]),
                reasoning=data["reasoning"]
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Fallback to default classification
            return ErrorClassification(
                severity=Severity.BLOCKING,
                stage=Stage.UNKNOWN,
                complexity=Complexity.MODERATE,
                reasoning=f"Failed to parse LLM response: {str(e)}"
            )


def classify_error_log(error_log: ErrorLog) -> ErrorClassification:
    """Convenience function to classify an error log using OpenAI."""

    classifier = ErrorClassifier()
    return classifier.classify(error_log)
