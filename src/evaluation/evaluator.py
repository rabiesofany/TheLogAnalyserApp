"""Evaluation framework for error classification system."""

import json
from typing import List, Dict
from dataclasses import dataclass, asdict

from src.parser.error_parser import parse_error_log
from src.classifier.error_classifier import classify_error_log
from src.fix_suggester.fix_suggester import generate_fix_suggestions
from src.evaluation.synthetic_generator import generate_synthetic_test_cases, GroundTruth


@dataclass
class EvaluationMetrics:
    """Metrics for evaluation results."""
    total_cases: int
    severity_accuracy: float
    stage_accuracy: float
    complexity_accuracy: float
    overall_accuracy: float
    avg_suggestion_count: float
    avg_confidence: float
    errors: List[Dict] = None


class ErrorClassificationEvaluator:
    """Evaluates the error classification system."""

    def __init__(self):
        """Initialize evaluator."""
        self.results = []

    def evaluate(self, test_cases: List[tuple]) -> EvaluationMetrics:
        """Run evaluation on test cases.

        Args:
            test_cases: List of (error_log, ground_truth) tuples

        Returns:
            EvaluationMetrics with results
        """
        print(f"Evaluating {len(test_cases)} test cases...")

        severity_correct = 0
        stage_correct = 0
        complexity_correct = 0
        total_suggestions = 0
        total_confidence = 0.0
        errors = []

        for i, (error_log, ground_truth) in enumerate(test_cases):
            print(f"Processing case {i+1}/{len(test_cases)}...", end="\r")

            try:
                # Parse and classify
                parsed_log = parse_error_log(error_log)
                classification = classify_error_log(parsed_log)
                suggestions = generate_fix_suggestions(
                    parsed_log,
                    classification
                )

                # Check accuracy
                if classification.severity.value == ground_truth.severity:
                    severity_correct += 1

                if classification.stage.value == ground_truth.stage:
                    stage_correct += 1

                if classification.complexity.value == ground_truth.complexity:
                    complexity_correct += 1

                # Track suggestions
                total_suggestions += len(suggestions)
                total_confidence += sum(s.confidence for s in suggestions) / len(suggestions)

                # Store result
                self.results.append({
                    "case_id": i,
                    "ground_truth": asdict(ground_truth),
                    "predicted": {
                        "severity": classification.severity.value,
                        "stage": classification.stage.value,
                        "complexity": classification.complexity.value,
                    },
                    "suggestions_count": len(suggestions),
                    "avg_confidence": sum(s.confidence for s in suggestions) / len(suggestions),
                    "correct": {
                        "severity": classification.severity.value == ground_truth.severity,
                        "stage": classification.stage.value == ground_truth.stage,
                        "complexity": classification.complexity.value == ground_truth.complexity,
                    }
                })

            except Exception as e:
                errors.append({
                    "case_id": i,
                    "error": str(e),
                    "ground_truth": asdict(ground_truth)
                })

        print()  # New line after progress

        # Calculate metrics
        total = len(test_cases)
        metrics = EvaluationMetrics(
            total_cases=total,
            severity_accuracy=severity_correct / total if total > 0 else 0.0,
            stage_accuracy=stage_correct / total if total > 0 else 0.0,
            complexity_accuracy=complexity_correct / total if total > 0 else 0.0,
            overall_accuracy=(severity_correct + stage_correct + complexity_correct) / (total * 3) if total > 0 else 0.0,
            avg_suggestion_count=total_suggestions / total if total > 0 else 0.0,
            avg_confidence=total_confidence / total if total > 0 else 0.0,
            errors=errors
        )

        return metrics

    def save_results(self, filename: str, metrics: EvaluationMetrics):
        """Save evaluation results to file.

        Args:
            filename: Output filename
            metrics: Evaluation metrics to save
        """
        output = {
            "metrics": asdict(metrics),
            "detailed_results": self.results
        }

        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"Results saved to {filename}")

    def print_report(self, metrics: EvaluationMetrics):
        """Print evaluation report.

        Args:
            metrics: Evaluation metrics to print
        """
        print("\n" + "=" * 60)
        print("EVALUATION REPORT")
        print("=" * 60)
        print(f"\nTotal Test Cases: {metrics.total_cases}")
        print(f"\nClassification Accuracy:")
        print(f"  Severity:   {metrics.severity_accuracy:.2%}")
        print(f"  Stage:      {metrics.stage_accuracy:.2%}")
        print(f"  Complexity: {metrics.complexity_accuracy:.2%}")
        print(f"  Overall:    {metrics.overall_accuracy:.2%}")
        print(f"\nFix Suggestions:")
        print(f"  Avg Count:      {metrics.avg_suggestion_count:.2f}")
        print(f"  Avg Confidence: {metrics.avg_confidence:.2%}")

        if metrics.errors:
            print(f"\nErrors Encountered: {len(metrics.errors)}")
            for error in metrics.errors[:5]:  # Show first 5
                print(f"  - Case {error['case_id']}: {error['error']}")

        print("=" * 60 + "\n")


def run_evaluation(test_case_count: int = 30) -> EvaluationMetrics:
    """Run complete evaluation.

    Args:
        test_case_count: Number of synthetic test cases to generate

    Returns:
        EvaluationMetrics
    """
    # Generate test cases
    print(f"Generating {test_case_count} synthetic test cases...")
    test_cases = generate_synthetic_test_cases(test_case_count)

    # Run evaluation
    evaluator = ErrorClassificationEvaluator()
    metrics = evaluator.evaluate(test_cases)

    # Print report
    evaluator.print_report(metrics)

    # Save results
    evaluator.save_results("evaluation_results.json", metrics)

    return metrics


if __name__ == "__main__":
    import sys
    import os

    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    # Get provider from command line or environment
    # we only support OpenAI so no provider argument required
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    run_evaluation(test_case_count=count)
