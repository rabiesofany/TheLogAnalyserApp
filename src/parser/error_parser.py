"""Parser for PLC compilation error logs."""

import re
from typing import List, Optional, Tuple
from src.models import ParsedError, ErrorLog, Stage, Severity, Complexity


class ErrorLogParser:
    """Parses multi-stage PLC compilation error logs."""

    # Regex patterns for different error types
    TIMESTAMP_PATTERN = r'\[(\d{2}:\d{2}:\d{2})\]'
    XML_ERROR_PATTERN = r'Warning: PLC XML file doesn\'t follow XSD schema at line (\d+):'
    IEC_ERROR_PATTERN = r'Warning: (.+?):(\d+)-\d+\.\.(\d+)-\d+: error: (.+)'
    PYTHON_TRACEBACK_START = r'stderr: Traceback \(most recent call last\):'
    ATTRIBUTE_ERROR_PATTERN = r'AttributeError: (.+)'
    FILE_LINE_PATTERN = r'File "(.+?)", line (\d+)'

    SEVERITY_MAP = {
        Stage.XML_VALIDATION: Severity.WARNING,
        Stage.CODE_GENERATION: Severity.BLOCKING,
        Stage.IEC_COMPILATION: Severity.BLOCKING,
        Stage.C_COMPILATION: Severity.BLOCKING,
        Stage.UNKNOWN: Severity.INFO,
    }

    COMPLEXITY_MAP = {
        Stage.XML_VALIDATION: Complexity.TRIVIAL,
        Stage.CODE_GENERATION: Complexity.MODERATE,
        Stage.IEC_COMPILATION: Complexity.TRIVIAL,
        Stage.C_COMPILATION: Complexity.COMPLEX,
        Stage.UNKNOWN: Complexity.MODERATE,
    }

    def parse(self, raw_log: str) -> ErrorLog:
        """Parse raw error log into structured format.

        Args:
            raw_log: Raw error log text

        Returns:
            ErrorLog object with parsed errors
        """
        lines = raw_log.strip().split('\n')
        errors = []

        # Check for XML validation errors
        xml_errors = self._parse_xml_errors(lines)
        errors.extend(xml_errors)

        # Check for IEC compilation errors
        iec_errors = self._parse_iec_errors(lines)
        errors.extend(iec_errors)

        # Check for Python tracebacks
        traceback_errors = self._parse_python_tracebacks(lines)
        errors.extend(traceback_errors)

        # Append build failure messages to the last root errors (no new events)
        self._attach_build_failure_details(lines, errors)

        # Determine if there are cascading errors
        has_cascading = self._detect_cascading_errors(errors, raw_log)

        return ErrorLog(
            raw_log=raw_log,
            errors=errors,
            has_cascading_errors=has_cascading
        )

    def _parse_xml_errors(self, lines: List[str]) -> List[ParsedError]:
        """Parse XML validation errors."""
        errors = []

        for i, line in enumerate(lines):
            match = re.search(self.XML_ERROR_PATTERN, line)
            if match:
                line_number = int(match.group(1))

                # Get context (next few lines)
                context = []
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    next_line = next_line.split("Start build", 1)[0].strip()
                    if next_line:
                        context.append(next_line)

                errors.append(ParsedError(
                    error_type="XMLValidationError",
                    message=line.strip(),
                    stage=Stage.XML_VALIDATION,
                    severity=self._severity_for_stage(Stage.XML_VALIDATION),
                    complexity=self._complexity_for_stage(Stage.XML_VALIDATION),
                    line_number=line_number,
                    context=context,
                    timestamp=self._extract_timestamp(lines[:i+1])
                ))

        return errors

    def _parse_iec_errors(self, lines: List[str]) -> List[ParsedError]:
        """Parse IEC compilation errors."""
        errors = []

        for i, line in enumerate(lines):
            match = re.search(self.IEC_ERROR_PATTERN, line)
            if match:
                file_path = match.group(1)
                line_number = int(match.group(2))
                error_message = match.group(4)

                # Get context (next few lines that start with "Warning:")
                context = []
                for j in range(i + 1, min(i + 4, len(lines))):
                    if lines[j].strip().startswith('Warning:'):
                        context.append(lines[j].strip())
                    else:
                        break

                errors.append(ParsedError(
                    error_type="IECCompilationError",
                    message=error_message,
                    stage=Stage.IEC_COMPILATION,
                    severity=self._severity_for_stage(Stage.IEC_COMPILATION),
                    complexity=self._complexity_for_stage(Stage.IEC_COMPILATION),
                    line_number=line_number,
                    file_path=file_path,
                    context=context,
                    timestamp=self._extract_timestamp(lines[:i+1])
                ))

        return errors

    def _parse_python_tracebacks(self, lines: List[str]) -> List[ParsedError]:
        """Parse Python traceback errors."""
        errors = []

        # Find traceback start
        for i, line in enumerate(lines):
            if re.search(self.PYTHON_TRACEBACK_START, line):
                # Extract full traceback
                traceback_lines = []
                error_type = None
                error_message = None
                file_path = None
                line_number = None

                # Collect all traceback lines
                for j in range(i, len(lines)):
                    current_line = lines[j]
                    traceback_lines.append(current_line)

                    # Check for AttributeError or other Python errors
                    attr_match = re.search(self.ATTRIBUTE_ERROR_PATTERN, current_line)
                    if attr_match:
                        error_type = "AttributeError"
                        error_message = attr_match.group(1)

                    # Extract file and line from the last File reference
                    file_match = re.search(self.FILE_LINE_PATTERN, current_line)
                    if file_match:
                        file_path = file_match.group(1)
                        line_number = int(file_match.group(2))

                if error_type:
                    errors.append(ParsedError(
                        error_type=error_type,
                        message=error_message or "Unknown error",
                        stage=Stage.CODE_GENERATION,
                        severity=self._severity_for_stage(Stage.CODE_GENERATION),
                        complexity=self._complexity_for_stage(Stage.CODE_GENERATION),
                        line_number=line_number,
                        file_path=file_path,
                        context=traceback_lines[-5:] if len(traceback_lines) > 5 else traceback_lines,
                        timestamp=self._extract_timestamp(lines[:i+1])
                    ))

                break  # Only process first traceback

        return errors

    def _attach_build_failure_details(self, lines: List[str], errors: List[ParsedError]) -> None:
        """Attach build failure / cascading messages as context to the last root error."""
        for line in lines:
            if "Error:" in line and "IEC to C compiler returned" in line:
                self._append_to_last_root_error(errors, line.strip())
            elif "PLC code generation failed" in line:
                self._append_to_last_root_error(errors, line.strip())

    def _append_to_last_root_error(self, errors: List[ParsedError], text: str) -> None:
        """Append text as context to the nearest root error (IEC first, then code generation, else last)."""
        target = None
        for error in reversed(errors):
            if error.stage == Stage.IEC_COMPILATION:
                target = error
                break

        if target is None:
            for error in reversed(errors):
                if error.stage == Stage.CODE_GENERATION:
                    target = error
                    break

        if target is None and errors:
            target = errors[-1]

        if target:
            if target.context is None:
                target.context = []
            target.context.append(text.strip())

    def _extract_timestamp(self, lines: List[str]) -> Optional[str]:
        """Extract the most recent timestamp from lines."""
        for line in reversed(lines):
            match = re.search(self.TIMESTAMP_PATTERN, line)
            if match:
                return match.group(1)
        return None

    def _detect_cascading_errors(self, errors: List[ParsedError], raw_log: str) -> bool:
        """Detect if errors are cascading from an earlier issue.

        Cascading occurs when an XML validation error leads to downstream errors.
        """
        if not errors:
            return False

        # Flag cascading when multiple errors exist
        return len(errors) > 1

    def _severity_for_stage(self, stage: Stage) -> Severity:
        """Return a default severity for the given stage."""
        return self.SEVERITY_MAP.get(stage, Severity.INFO)

    def _complexity_for_stage(self, stage: Stage) -> Complexity:
        """Return a default complexity for the given stage."""
        return self.COMPLEXITY_MAP.get(stage, Complexity.MODERATE)


def parse_error_log(raw_log: str) -> ErrorLog:
    """Convenience function to parse an error log.

    Args:
        raw_log: Raw error log text

    Returns:
        Parsed ErrorLog object
    """
    parser = ErrorLogParser()
    return parser.parse(raw_log)
