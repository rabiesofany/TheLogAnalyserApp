"""Data models for error classification system."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Error severity levels."""
    BLOCKING = "blocking"
    WARNING = "warning"
    INFO = "info"


class Stage(str, Enum):
    """Build pipeline stages."""
    XML_VALIDATION = "xml_validation"
    CODE_GENERATION = "code_generation"
    IEC_COMPILATION = "iec_compilation"
    C_COMPILATION = "c_compilation"
    UNKNOWN = "unknown"


class Complexity(str, Enum):
    """Fix complexity levels."""
    TRIVIAL = "trivial"
    MODERATE = "moderate"
    COMPLEX = "complex"


class ParsedError(BaseModel):
    """Represents a single parsed error from the log."""
    error_type: str = Field(..., description="Type of error (e.g., 'AttributeError', 'CompilationError')")
    message: str = Field(..., description="Full error message")
    stage: Stage = Field(..., description="Pipeline stage where error occurred")
    severity: Severity = Field(..., description="Severity assigned to this error")
    line_number: Optional[int] = Field(None, description="Line number if available")
    file_path: Optional[str] = Field(None, description="File path if available")
    context: List[str] = Field(default_factory=list, description="Surrounding context lines")
    timestamp: Optional[str] = Field(None, description="Timestamp if available")
    is_cascading: bool = Field(False, description="Whether this error is caused by another error")


class ErrorLog(BaseModel):
    """Complete parsed error log."""
    raw_log: str = Field(..., description="Original unparsed log")
    errors: List[ParsedError] = Field(default_factory=list, description="All parsed errors")
    has_cascading_errors: bool = Field(False, description="Whether log contains cascading errors")


class ErrorClassification(BaseModel):
    """Classification result for an error."""
    severity: Severity
    stage: Stage
    complexity: Complexity
    reasoning: str = Field(..., description="Explanation for the classification")

class ErrorInsight(BaseModel):
    """Per-error stage insight."""
    stage: Stage = Field(..., description="Stage where this error was encountered")
    severity: Severity = Field(..., description="Severity assigned to this stage")
    complexity: Complexity = Field(..., description="Complexity level of the fix")
    line_number: Optional[int] = Field(None, description="Line number of the error")
    file_path: Optional[str] = Field(None, description="File path tied to the error")
    snippet: Optional[str] = Field(None, description="Short summary/snippet for display")


class FixSuggestion(BaseModel):
    """A single fix suggestion."""
    title: str = Field(..., description="Short title for the fix")
    description: str = Field(..., description="Detailed explanation of the fix")
    root_cause: str = Field(..., description="Explanation of why the error occurred")
    code_before: Optional[str] = Field(None, description="Code snippet before fix")
    code_after: Optional[str] = Field(None, description="Code snippet after fix")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")


class ClassificationResponse(BaseModel):
    """Complete response for error classification request."""
    classification: ErrorClassification
    suggestions: List[FixSuggestion] = Field(..., min_items=1, max_items=3)
    parsed_errors: List[ParsedError] = Field(default_factory=list, description="All parsed errors from log")
    error_insights: List[ErrorInsight] = Field(
        default_factory=list,
        description="Per-error stage insights for the log"
    )


class ClassificationRequest(BaseModel):
    """Request model for error classification."""
    error_log: str = Field(..., description="Raw error log text to classify")
