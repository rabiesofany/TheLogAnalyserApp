"""Tests for error log parser."""

import pytest
from src.parser.error_parser import ErrorLogParser, parse_error_log
from src.models import Stage


class TestErrorLogParser:
    """Test cases for ErrorLogParser."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = ErrorLogParser()

        self.constant_error_log = """[17:05:55]: Building project...
[17:05:56]: Cannot build project.
stdout: Warning: PLC XML file doesn't follow XSD schema at line 61:
Element '{http://www.plcopen.org/xml/tc6_0201}data': Missing child element(s).
Generating SoftPLC IEC-61131 ST/IL/SFC code...
Compiling IEC Program into C code...
Warning: /tmp/.tmpMngQvj/build/plc.st:30-4..30-12: error: Assignment to CONSTANT variables is not allowed.
Warning: In section: PROGRAM program0
Warning: 0030: LocalVar1 := LocalVar0;
Error: Error : IEC to C compiler returned 1
Error: PLC code generation failed !"""

        self.empty_project_log = """[18:16:53]: Building project...
stdout: Warning: PLC XML file doesn't follow XSD schema at line 43:
Generating SoftPLC IEC-61131 ST/IL/SFC code...
stderr: Traceback (most recent call last):
  File "/root/beremiz/Beremiz_cli.py", line 130, in <module>
    cli()
  File "/root/beremiz/PLCGenerator.py", line 959, in ComputeProgram
    self.ParentGenerator.GeneratePouProgramInText(text.upper())
AttributeError: 'NoneType' object has no attribute 'upper'"""

    def test_parse_constant_error(self):
        """Test parsing constant assignment error."""
        result = self.parser.parse(self.constant_error_log)

        assert len(result.errors) > 0
        assert result.has_cascading_errors

        # Check for XML error
        xml_errors = [e for e in result.errors if e.stage == Stage.XML_VALIDATION]
        assert len(xml_errors) > 0
        assert xml_errors[0].line_number == 61

        # Check for IEC error
        iec_errors = [e for e in result.errors if e.stage == Stage.IEC_COMPILATION]
        assert len(iec_errors) > 0

    def test_parse_empty_project_error(self):
        """Test parsing empty project error."""
        result = self.parser.parse(self.empty_project_log)

        assert len(result.errors) > 0

        # Check for Python traceback
        traceback_errors = [e for e in result.errors if e.error_type == "AttributeError"]
        assert len(traceback_errors) > 0
        assert "NoneType" in traceback_errors[0].message

    def test_parse_xml_errors(self):
        """Test XML validation error parsing."""
        errors = self.parser._parse_xml_errors(self.constant_error_log.split('\n'))

        assert len(errors) == 1
        assert errors[0].error_type == "XMLValidationError"
        assert errors[0].line_number == 61
        assert errors[0].stage == Stage.XML_VALIDATION

    def test_parse_iec_errors(self):
        """Test IEC compilation error parsing."""
        errors = self.parser._parse_iec_errors(self.constant_error_log.split('\n'))

        assert len(errors) == 1
        assert errors[0].error_type == "IECCompilationError"
        assert errors[0].line_number == 30
        assert errors[0].stage == Stage.IEC_COMPILATION
        assert "CONSTANT" in errors[0].message

    def test_parse_python_tracebacks(self):
        """Test Python traceback parsing."""
        errors = self.parser._parse_python_tracebacks(self.empty_project_log.split('\n'))

        assert len(errors) == 1
        assert errors[0].error_type == "AttributeError"
        assert errors[0].stage == Stage.CODE_GENERATION

    def test_extract_timestamp(self):
        """Test timestamp extraction."""
        lines = ["[17:05:55]: Building project...", "Some other line"]
        timestamp = self.parser._extract_timestamp(lines)

        assert timestamp == "17:05:55"

    def test_detect_cascading_errors(self):
        """Test cascading error detection."""
        from src.models import ParsedError

        errors = [
            ParsedError(
                error_type="XMLValidationError",
                message="XML error",
                stage=Stage.XML_VALIDATION
            ),
            ParsedError(
                error_type="IECCompilationError",
                message="IEC error",
                stage=Stage.IEC_COMPILATION
            )
        ]

        has_cascading = self.parser._detect_cascading_errors(errors, "test log")

        assert has_cascading
        assert errors[1].is_cascading

    def test_parse_empty_log(self):
        """Test parsing empty log."""
        result = self.parser.parse("")

        assert len(result.errors) == 0
        assert not result.has_cascading_errors

    def test_convenience_function(self):
        """Test convenience function."""
        result = parse_error_log(self.constant_error_log)

        assert isinstance(result.errors, list)
        assert len(result.errors) > 0
