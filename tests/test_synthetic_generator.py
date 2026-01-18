"""Tests for synthetic error generator."""

import pytest
from src.evaluation.synthetic_generator import (
    SyntheticErrorGenerator,
    generate_synthetic_test_cases
)


class TestSyntheticErrorGenerator:
    """Test cases for SyntheticErrorGenerator."""

    def setup_method(self):
        """Set up test fixtures."""
        self.generator = SyntheticErrorGenerator()

    def test_generate_test_cases(self):
        """Test test case generation."""
        test_cases = self.generator.generate_test_cases(count=10)

        assert len(test_cases) == 10

        for error_log, ground_truth in test_cases:
            assert isinstance(error_log, str)
            assert len(error_log) > 0
            assert hasattr(ground_truth, 'severity')
            assert hasattr(ground_truth, 'stage')
            assert hasattr(ground_truth, 'complexity')

    def test_generate_constant_error(self):
        """Test constant error generation."""
        error_log, ground_truth = self.generator._generate_constant_error()

        assert "Assignment to CONSTANT variables" in error_log
        assert ground_truth.severity == "blocking"
        assert ground_truth.stage == "iec_compilation"
        assert ground_truth.complexity == "trivial"

    def test_generate_empty_project_error(self):
        """Test empty project error generation."""
        error_log, ground_truth = self.generator._generate_empty_project_error()

        assert "AttributeError" in error_log
        assert "NoneType" in error_log
        assert ground_truth.severity == "blocking"
        assert ground_truth.stage == "code_generation"
        assert ground_truth.complexity == "moderate"

    def test_random_timestamp(self):
        """Test timestamp generation."""
        timestamp = self.generator._random_timestamp()

        assert len(timestamp) == 8
        assert timestamp.count(":") == 2

        # Parse timestamp
        parts = timestamp.split(":")
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2])

        assert 10 <= hour <= 23
        assert 0 <= minute <= 59
        assert 0 <= second <= 59

    def test_convenience_function(self):
        """Test convenience function."""
        test_cases = generate_synthetic_test_cases(count=5)

        assert len(test_cases) == 5

    def test_error_variation(self):
        """Test that generated errors have variation."""
        test_cases = self.generator.generate_test_cases(count=20)

        # Extract some varying parameters
        xml_lines = set()
        error_lines = set()

        for error_log, _ in test_cases:
            if "line " in error_log:
                # Extract line numbers to verify variation
                lines = error_log.split('\n')
                for line in lines:
                    if "schema at line" in line:
                        # Extract XML line number
                        parts = line.split("line ")
                        if len(parts) > 1:
                            num = parts[1].split(":")[0]
                            xml_lines.add(num)

        # Should have multiple different line numbers
        assert len(xml_lines) > 1
