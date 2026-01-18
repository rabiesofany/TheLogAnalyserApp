# Quick Start Guide

## Get Started in 5 Minutes

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. Configure API Key

```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your API key
# Anthropic:
#   ANTHROPIC_API_KEY=your_key_here
```

### 3. Test the Parser

```python
# Quick test without API calls
from src.parser.error_parser import parse_error_log

with open('sample_data/constant_error.txt', 'r') as f:
    log = f.read()

result = parse_error_log(log)
print(f"Found {len(result.errors)} errors")
for error in result.errors:
    print(f"  - {error.error_type} at {error.stage.value}")
```

### 4. Run the API

```bash
python run_api.py
```

Visit: http://localhost:8000/docs

### 5. Test the API

```bash
# Using curl
curl -X POST "http://localhost:8000/classify" \
  -H "Content-Type: application/json" \
  -d @- <<'EOF'
{
  "error_log": "[17:05:55]: Building project...\n[17:05:56]: Cannot build project.\nstdout: Warning: PLC XML file doesn't follow XSD schema at line 61:\nElement '{http://www.plcopen.org/xml/tc6_0201}data': Missing child element(s). Expected is one of ( {*}*, * ).Start build in /tmp/.tmpMngQvj/build\nGenerating SoftPLC IEC-61131 ST/IL/SFC code...\nCompiling IEC Program into C code...\nWarning: /tmp/.tmpMngQvj/build/plc.st:30-4..30-12: error: Assignment to CONSTANT variables is not allowed.\nError: Error : IEC to C compiler returned 1"
}
EOF
```

### 6. Run Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test
pytest tests/test_parser.py -v
```

### 7. Run Evaluation

```bash
# Run evaluation with 30 test cases
python -m src.evaluation.evaluator

# Results saved to evaluation_results.json
```

## Python Usage Examples

### Example 1: Parse Only

```python
from src.parser.error_parser import parse_error_log

log_text = """[17:05:55]: Building project...
Warning: Error at line 30..."""

result = parse_error_log(log_text)
print(f"Errors found: {len(result.errors)}")
print(f"Has cascading errors: {result.has_cascading_errors}")
```

### Example 2: Full Classification

```python
from src.parser.error_parser import parse_error_log
from src.classifier.error_classifier import classify_error_log
from src.fix_suggester.fix_suggester import generate_fix_suggestions

# Parse
error_log = parse_error_log(log_text)

# Classify
classification = classify_error_log(error_log)
print(f"Severity: {classification.severity.value}")
print(f"Stage: {classification.stage.value}")
print(f"Complexity: {classification.complexity.value}")

# Get suggestions
suggestions = generate_fix_suggestions(error_log, classification)
for i, suggestion in enumerate(suggestions, 1):
    print(f"\nSuggestion {i}: {suggestion.title}")
    print(f"Confidence: {suggestion.confidence:.2%}")
```

### Example 3: Programmatic API Usage

```python
import requests

response = requests.post(
    "http://localhost:8000/classify",
    json={"error_log": log_text}
)

result = response.json()
print(f"Classification: {result['classification']}")
print(f"Suggestions: {len(result['suggestions'])}")
```

## Troubleshooting

### Import Errors

If you see import errors, make sure you're in the project root and have activated the virtual environment:

```bash
# Add project to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### API Key Errors

Make sure your `.env` file exists and contains the correct API key:

```bash
cat .env  # Check contents
```

### LLM Timeout

If requests timeout, the LLM might be slow. Increase timeouts or try a different model.

## Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Explore the code in `src/` directory
- Run the evaluation framework to see performance metrics
- Integrate with your own PLC error logs

## Sample Data

The `sample_data/` directory contains two example error logs:
- `constant_error.txt` - IEC compilation error (constant assignment)
- `empty_project.txt` - Code generation error (AttributeError)

Use these for testing!
