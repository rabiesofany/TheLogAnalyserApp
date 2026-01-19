"""Fix suggestion system using Anthropic."""

import json
import os
from typing import List, Optional
from anthropic import Anthropic

from src.models import (
    Complexity,
    ErrorClassification,
    ErrorLog,
    FixSuggestion,
    ParsedError,
    Stage,
    Severity,
)


class FixSuggester:
    """Generates fix suggestions for PLC compilation errors."""

    def __init__(self, model: Optional[str] = None):
        """Initialize the fix suggester with Anthropic."""
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model or "claude-haiku-4-5-20251001"

    def suggest_fixes(
        self,
        error_log: ErrorLog,
        classification: ErrorClassification
    ) -> List[FixSuggestion]:
        """Generate fix suggestions for the entire log by targeting each parsed error."""
        all_suggestions = []
        for idx, error in enumerate(error_log.errors):
            suggestions = self.suggest_fixes_for_error(error_log, classification, idx, error)
            all_suggestions.extend(suggestions)
        return all_suggestions

    def _build_fix_prompt(
        self,
        error_log: ErrorLog,
        classification: ErrorClassification
    ) -> str:
        """Build the fix suggestion prompt."""
        errors_detail = "\n".join([
            f"""Error {i+1}:
  Type: {e.error_type}
  Stage: {e.stage.value}
  Message: {e.message}
  Line: {e.line_number or 'N/A'}
  File: {e.file_path or 'N/A'}
  Context: {e.context[:2] if e.context else 'None'}"""
            for i, e in enumerate(error_log.errors)
        ])

        prompt = f"""You are an expert at fixing PLC (Programmable Logic Controller) compilation errors.

Analyze the following error and provide 1-3 actionable fix suggestions.

**Error Classification:**
- Severity: {classification.severity.value}
- Stage: {classification.stage.value}
- Complexity: {classification.complexity.value}
- Reasoning: {classification.reasoning}

**Errors Found:**
{errors_detail}

**Full Error Log:**
{error_log.raw_log[:2000]}

**Instructions:**
1. Provide 1-3 distinct fix suggestions, ordered by likelihood of success
2. For each suggestion, include:
   - A short, clear title
   - Detailed description of what to do
   - Root cause explanation (why did this error occur?)
   - Code snippets showing before/after (if applicable)
   - Confidence score (0.0-1.0)

3. If the error involves cascading issues, prioritize fixing the root cause first
4. If context is missing, acknowledge it and provide best-effort suggestions

Include `error_index` for each suggestion so we know which parsed error the recommendation targets (0 = first error in the log). Ensure `error_index` matches the order the errors are described above.

Respond ONLY with a JSON array in this exact format:
[
  {{
    "title": "Fix title",
    "description": "Detailed explanation of the fix",
    "root_cause": "Why this error occurred",
    "code_before": "// Before code (or null if not applicable)",
    "code_after": "// After code (or null if not applicable)",
    "confidence": 0.0,
    "error_index": 0
  }}
]

Provide 1-3 suggestions, include the zero-based index of the parsed error that each suggestion addresses (`error_index`), and use a realistic confidence score (0.0–1.0) so the field varies per response."""

        return prompt

    def _build_error_fix_prompt(
        self,
        error_log: ErrorLog,
        classification: ErrorClassification,
        error_index: int,
        error: ParsedError
    ) -> str:
        """Build a prompt focused on a single parsed error."""
        context_snippet = "\n".join([f"- {line}" for line in error.context]) if error.context else "No extra context available."
        prompt = f"""You are an expert at fixing PLC (Programmable Logic Controller) compilation errors.

Focus on this parsed error (index {error_index + 1}):
- Severity: {error.severity.value}
- Stage: {error.stage.value}
- Complexity: {classification.complexity.value}
- Message: {error.message}
- File: {error.file_path or 'N/A'}
- Line: {error.line_number or 'N/A'}
- Context:
{context_snippet}

Provide 1-3 actionable fix suggestions tailored to this error. Each suggestion must include:
  - title
  - description
  - root cause
  - code_before (or null)
  - code_after (or null)
  - confidence (0.0-1.0)
  - error_index ({error_index})

Respond only with a JSON array in this exact format:
[
  {{
    "title": "Fix title",
    "description": "Detailed explanation of the fix",
    "root_cause": "Why this error occurred",
    "code_before": "// Before code (or null if not applicable)",
    "code_after": "// After code (or null if not applicable)",
    "confidence": 0.0,
    "error_index": {error_index}
  }}
]

Ensure the `error_index` returns the provided value so the client can attach suggestions to the correct parsed error."""

        return prompt

    def suggest_fixes_for_error(
        self,
        error_log: ErrorLog,
        classification: ErrorClassification,
        error_index: int,
        error: ParsedError
    ) -> List[FixSuggestion]:
        prompt = self._build_error_fix_prompt(error_log, classification, error_index, error)
        response = self._call_anthropic(prompt)
        return self._parse_fix_response(response, classification, error_index=error_index)

    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def _parse_fix_response(self, response: str, classification: ErrorClassification, error_index: int = 0) -> List[FixSuggestion]:
        """Parse LLM response into FixSuggestions."""
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

            suggestions = []
            for idx, item in enumerate(data[:3]):  # Max 3 suggestions
                suggestions.append(FixSuggestion(
                    title=item["title"],
                    description=item["description"],
                    root_cause=item["root_cause"],
                    code_before=item.get("code_before"),
                    code_after=item.get("code_after"),
                    confidence=self._deterministic_confidence(classification, idx)
                    ,
                    error_index=int(item.get("error_index", idx))
                ))

            # Ensure at least one suggestion
            if not suggestions:
                suggestions = [self._default_suggestion(
                    self._deterministic_confidence(classification, 0),
                    error_index=0
                )]

            return suggestions

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Return default suggestion on error
            return [self._default_suggestion(
                self._deterministic_confidence(classification, 0),
                error_index=0
            )]

    def _default_suggestion(self, confidence: float = 0.3, error_index: int = 0) -> FixSuggestion:
        """Create a default suggestion when parsing fails."""
        return FixSuggestion(
            title="Review Error Log",
            description="Unable to generate specific fix suggestions. Please review the error log and check for common issues like syntax errors, type mismatches, or missing declarations.",
            root_cause="Insufficient context to determine root cause",
            code_before=None,
            code_after=None,
            confidence=confidence
            ,
            error_index=error_index
        )

    def _deterministic_confidence(self, classification: ErrorClassification, suggestion_index: int) -> float:
        """Compute a repeatable confidence score based on the classification."""
        severity_weights = {
            Severity.BLOCKING: 0.9,
            Severity.WARNING: 0.6,
            Severity.INFO: 0.4,
        }
        complexity_weights = {
            Complexity.TRIVIAL: 0.5,
            Complexity.MODERATE: 0.65,
            Complexity.COMPLEX: 0.8,
        }

        stage_offsets = {
            Stage.XML_VALIDATION: 0.0,
            Stage.CODE_GENERATION: 0.03,
            Stage.IEC_COMPILATION: 0.05,
            Stage.C_COMPILATION: 0.07,
            Stage.UNKNOWN: 0.0,
        }

        severity_score = severity_weights.get(classification.severity, 0.5)
        complexity_score = complexity_weights.get(classification.complexity, 0.6)
        stage_score = stage_offsets.get(classification.stage, 0.0)

        base_confidence = (severity_score + complexity_score) / 2
        adjusted = base_confidence + stage_score - (suggestion_index * 0.02)
        return float(max(0.0, min(1.0, adjusted)))


def generate_fix_suggestions(
    error_log: ErrorLog,
    classification: ErrorClassification,
) -> List[FixSuggestion]:
    """Convenience function to generate fix suggestions using OpenAI.

    Args:
        error_log: Parsed error log
        classification: Error classification

    Returns:
        List of fix suggestions
    """
    suggester = FixSuggester()
    return suggester.suggest_fixes(error_log, classification)
