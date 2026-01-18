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

        prompt = f"""You are an expert at analyzing PLC (Programmable Logic Controller) compilation errors.

Analyze the following error log and classify it according to these criteria:

**Severity:**
- blocking: Prevents compilation/execution completely
- warning: Can proceed but may cause issues
- info: Informational only

**Stage:**
- xml_validation: XML schema validation errors
- code_generation: IEC code generation errors
- iec_compilation: IEC to C compilation errors
- c_compilation: C compiler errors
- unknown: Cannot determine stage

**Fix Complexity:**
- trivial: Simple fix (e.g., syntax error, missing semicolon)
- moderate: Requires some understanding (e.g., type mismatch, logic error)
- complex: Deep understanding needed (e.g., architecture change, cascading errors)

**Error Log Summary:**
{errors_summary}

**Full Error Log:**
{error_log.raw_log[:2000]}

**Cascading Errors:** {error_log.has_cascading_errors}

Respond ONLY with a JSON object in this exact format:
{{
    "severity": "blocking|warning|info",
    "stage": "xml_validation|code_generation|iec_compilation|c_compilation|unknown",
    "complexity": "trivial|moderate|complex",
    "reasoning": "Brief explanation of your classification"
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
