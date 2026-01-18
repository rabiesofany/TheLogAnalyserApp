"""Synthetic error log generator for testing."""

import random
from typing import List, Dict
from dataclasses import dataclass


@dataclass
class GroundTruth:
    """Ground truth labels for a test case."""
    severity: str
    stage: str
    complexity: str
    description: str


class SyntheticErrorGenerator:
    """Generates synthetic error logs based on base templates."""

    # Base templates
    CONSTANT_ERROR_TEMPLATE = """[{timestamp}]: Building project...
[{timestamp}]: Cannot build project.
[{timestamp}]: Cannot build project.
stdout: Warning: PLC XML file doesn't follow XSD schema at line {xml_line}:
Element '{{http://www.plcopen.org/xml/tc6_0201}}data': Missing child element(s). Expected is one of ( {{*}}*, * ).Start build in /tmp/.{build_dir}/build
Generating SoftPLC IEC-61131 ST/IL/SFC code...
Collecting data types
Collecting POUs
Generate POU program0
Generate Config(s)
Compiling IEC Program into C code...
0.000s 0.101s 0.201s 0.301s
"/root/beremiz/matiec/iec2c" -f -l -p -I "/root/beremiz/matiec/lib" -T "/tmp/.{build_dir}/build" "/tmp/.{build_dir}/build/plc.st"
Warning: exited with status 1 (pid {pid})
0.342s
Warning: /tmp/.{build_dir}/build/plc.st:{error_line}-4..{error_line}-12: error: Assignment to CONSTANT variables is not allowed.
Warning: In section: PROGRAM {program_name}
Warning: {line_marker}: {var1} := {var2};
Warning: 1 error(s) found. Bailing out!
Warning:
Error: Error : IEC to C compiler returned 1
Error: PLC code generation failed !
"""

    EMPTY_PROJECT_TEMPLATE = """[{timestamp}]: Building project...
[{timestamp}]: Cannot build project.
[{timestamp}]: Cannot build project.
stdout: Warning: PLC XML file doesn't follow XSD schema at line {xml_line}:
Element '{{http://www.plcopen.org/xml/tc6_0201}}data': Missing child element(s). Expected is one of ( {{*}}*, * ).Start build in /tmp/.{build_dir}/build
Generating SoftPLC IEC-61131 ST/IL/SFC code...
Collecting data types
Collecting POUs
Generate POU program0

stderr: Traceback (most recent call last):
  File "/root/beremiz/Beremiz_cli.py", line 130, in <module>
    cli()
  File "/usr/local/lib/python3.10/dist-packages/click/core.py", line 1130, in __call__
    return self.main(*args, **kwargs)
  File "/usr/local/lib/python3.10/dist-packages/click/core.py", line 1055, in main
    rv = self.invoke(ctx)
  File "/root/beremiz/PLCGenerator.py", line {error_line}, in ComputeProgram
    self.ParentGenerator.GeneratePouProgramInText({attribute}.upper())
AttributeError: '{none_type}' object has no attribute 'upper'
"""

    VARIABLE_NAMES = ["LocalVar0", "LocalVar1", "GlobalVar", "TempVar", "ConfigVar", "StatusFlag"]
    PROGRAM_NAMES = ["program0", "main_program", "control_loop", "init_sequence"]
    BUILD_DIRS = ["tmpMngQvj", "tmpL3UKDb", "tmpXkz9Pw", "tmpQrs4Tu"]

    def generate_test_cases(self, count: int = 30) -> List[tuple]:
        """Generate synthetic test cases with ground truth.

        Args:
            count: Number of test cases to generate

        Returns:
            List of (error_log, ground_truth) tuples
        """
        test_cases = []

        # Generate approximately 60% constant errors, 40% empty project errors
        constant_count = int(count * 0.6)
        empty_count = count - constant_count

        # Generate constant assignment errors
        for _ in range(constant_count):
            error_log, ground_truth = self._generate_constant_error()
            test_cases.append((error_log, ground_truth))

        # Generate empty project errors
        for _ in range(empty_count):
            error_log, ground_truth = self._generate_empty_project_error()
            test_cases.append((error_log, ground_truth))

        # Shuffle to mix them up
        random.shuffle(test_cases)

        return test_cases

    def _generate_constant_error(self) -> tuple:
        """Generate a constant assignment error variant."""
        params = {
            "timestamp": self._random_timestamp(),
            "xml_line": random.randint(20, 100),
            "build_dir": random.choice(self.BUILD_DIRS),
            "pid": random.randint(100, 999),
            "error_line": random.randint(20, 50),
            "program_name": random.choice(self.PROGRAM_NAMES),
            "line_marker": f"{random.randint(20, 50):04d}",
            "var1": random.choice(self.VARIABLE_NAMES),
            "var2": random.choice(self.VARIABLE_NAMES),
        }

        error_log = self.CONSTANT_ERROR_TEMPLATE.format(**params)

        ground_truth = GroundTruth(
            severity="blocking",
            stage="iec_compilation",
            complexity="trivial",
            description="Assignment to CONSTANT variable in IEC code"
        )

        return error_log, ground_truth

    def _generate_empty_project_error(self) -> tuple:
        """Generate an empty project error variant."""
        params = {
            "timestamp": self._random_timestamp(),
            "xml_line": random.randint(20, 100),
            "build_dir": random.choice(self.BUILD_DIRS),
            "error_line": random.randint(900, 1000),
            "attribute": random.choice(["text", "value", "content", "data"]),
            "none_type": "NoneType",
        }

        error_log = self.EMPTY_PROJECT_TEMPLATE.format(**params)

        ground_truth = GroundTruth(
            severity="blocking",
            stage="code_generation",
            complexity="moderate",
            description="AttributeError due to None object during code generation"
        )

        return error_log, ground_truth

    def _random_timestamp(self) -> str:
        """Generate a random timestamp."""
        hour = random.randint(10, 23)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        return f"{hour:02d}:{minute:02d}:{second:02d}"


def generate_synthetic_test_cases(count: int = 30) -> List[tuple]:
    """Convenience function to generate test cases.

    Args:
        count: Number of test cases to generate

    Returns:
        List of (error_log, ground_truth) tuples
    """
    generator = SyntheticErrorGenerator()
    return generator.generate_test_cases(count)
