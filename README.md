# PLC Error Classification System

An AI-powered system that classifies PLC (Programmable Logic Controller) compilation errors and suggests actionable fixes. This system helps engineers quickly diagnose and resolve cryptic errors across multiple build pipeline stages.

## Overview

OTee's customers develop PLC logic programs that go through a multi-stage build pipeline:
1. XML validation
2. IEC code generation
3. IEC compilation
4. C compilation

Engineers often spend hours debugging cryptic errors that span multiple stages. This system automates error classification and provides intelligent fix suggestions with code examples.

## Features

- **Multi-Stage Error Parsing**: Parses complex, multi-line error logs from all pipeline stages
- **AI-Powered Classification**: Classifies errors by severity, stage, and fix complexity
- **Intelligent Fix Suggestions**: Generates 1-3 actionable fix suggestions with code examples
- **Cascading Error Detection**: Identifies when errors are caused by upstream issues
- **HTTP API**: Fast REST API for integration (< 3 second response time)
- **Evaluation Framework**: Automated testing with synthetic error generation ( Conducted on External system, synthetic data & generated evaluation results are uploaded to the project)

## Project Structure

```
.
├── src/
│   ├── api/
│   │   ├── __init__.py
│   │   └── main.py                    # FastAPI application
│   ├── classifier/
│   │   ├── __init__.py
│   │   └── error_classifier.py        # LLM-based classifier
│   ├── parser/
│   │   ├── __init__.py
│   │   └── error_parser.py            # Error log parser
│   ├── fix_suggester/
│   │   ├── __init__.py
│   │   └── fix_suggester.py           # Fix suggestion generator
│   └── models.py                      # Pydantic data models
├── evaluation/
│   ├── __init__.py
│   ├── synthetic_generator.py         # Synthetic error generator
│   └── evaluator.py                   # Evaluation framework
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_api.py
│   └── test_synthetic_generator.py
├── sample_data/
│   ├── constant_error.txt
│   └── empty_project.txt
├── scripts/
│   ├── system_validation_script.sh
│   ├── curl_system.sh
│   └── stream_error_log.sh
├── logs/
│   └── system_validation/             # Validation outputs
├── plc_log_samples.csv
├── curl_output.json
├── requirements.txt
├── run_api.py                          # API server runner
├── QUICKSTART.md
├── PROJECT_SUMMARY.md
├── .env.example                        # Environment template
├── README.md
├── Dockerfile
├── fly.toml
└── pytest.ini
```

## Installation

### Prerequisites

- Python 3.9+
- API key for Anthropic Claude (the service uses `claude-haiku-4-5-20251001` by default)

### Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-task-bundle
```

2. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env and add your API key
```

Example `.env`:
```
# Anthropic configuration
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
```

### Discover available Anthropic models

Once your `.env` is configured, load the file so the API key is available to shell commands and then hit Anthropic’s `/v1/models` endpoint to list the models your account can use:
```
set -a
source .env
set +a

curl https://api.anthropic.com/v1/models \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01"
```

The response shows every Anthropic model the supplied key can call, which you can then copy into `src/classifier/error_classifier.py` / `src/fix_suggester/fix_suggester.py` if you want to override the defaults.

## Usage

### Running the API

Start the API server:
```bash
python run_api.py
```

The API will be available at `http://localhost:8001`

API documentation: `http://localhost:8001/docs`

### API Endpoints

#### POST /classify

Classify an error log and get fix suggestions.

**Request:**
```json
{
  "error_log": "string containing the full error log"
}
```

**Response:**
```json
{
  "classification": {
    "severity": "blocking|warning|info",
    "stage": "xml_validation|code_generation|iec_compilation|c_compilation",
    "complexity": "trivial|moderate|complex",
    "reasoning": "Explanation of classification"
  },
  "suggestions": [
    {
      "title": "Fix title",
      "description": "Detailed explanation",
      "root_cause": "Why the error occurred",
      "code_before": "Code before fix (if applicable)",
      "code_after": "Code after fix (if applicable)",
      "confidence": 0.85
    }
  ],
  "parsed_errors": [
    {
      "error_type": "string",
      "message": "string",
      "stage": "string",
      "line_number": 30,
      "file_path": "string",
      "context": ["array of context lines"],
      "timestamp": "17:05:55"
    }
  ]
}
```

**Example with curl:**
```bash
curl -X POST "http://localhost:8001/classify" \
  -H "Content-Type: application/json" \
  -d '{
    "error_log": "[17:05:55]: Building project...\n[17:05:56]: Cannot build project.\nWarning: PLC XML file doesn'\''t follow XSD schema at line 61..."
  }'
```

### Running Tests

Run the test suite:
```bash
pytest tests/ -v
```

Run specific test file:
```bash
pytest tests/test_parser.py -v
```

Run with coverage:
```bash
pytest tests/ --cov=src --cov-report=html
```

### Running Evaluation

Evaluate the system on synthetic test cases:

```bash
python -m src.evaluation.evaluator
```

With custom parameters:
```bash
python -m src.evaluation.evaluator 30
```

This will:
1. Generate 30 synthetic test cases
2. Classify each one
3. Compare against ground truth
4. Print evaluation report
5. Save detailed results to `evaluation_results.json`

## Architecture Decisions

### 1. Parser Design

**Decision**: Multi-pass parsing with specialized regex patterns for each error type.

**Rationale**:
- PLC error logs contain multiple distinct formats (XML validation, IEC compilation, Python tracebacks)
- Single-pass parsing would be overly complex
- Specialized parsers are easier to test and maintain
- Allows for easy addition of new error types

-### 2. LLM Integration

**Decision**: Rely on Anthropic Claude (`claude-haiku-4-5-20251001`) as the single provider for classification and suggestions.

**Rationale**:
- Simplifies configuration and avoids provider-specific key handling
- Claude is purpose-built for structured tasks and JSON adherence
- Controls costs while still providing reliable logic for PLC errors

### 3. Classification Strategy

**Decision**: Use structured prompts with explicit JSON output format.

**Rationale**:
- Ensures consistent, parseable responses
- Reduces hallucination by constraining output format
- Makes evaluation straightforward
- Few-shot examples embedded in prompt improve accuracy

### 4. API Framework

**Decision**: FastAPI over Flask.

**Rationale**:
- Automatic OpenAPI documentation
- Built-in request validation with Pydantic
- Native async support for better performance
- Type hints throughout improve code quality
- Modern Python features and excellent developer experience

### 5. Evaluation Approach

**Decision**: Synthetic error generation with parameterized templates.

**Rationale**:
- Real error logs are limited in quantity
- Synthetic generation allows for extensive testing
- Parameterization ensures variation while maintaining realism
- Ground truth labels are accurate by construction
- Can generate unlimited test cases on demand

### 6. Error Representation

**Decision**: Pydantic models for all data structures.

**Rationale**:
- Automatic validation ensures data integrity
- Clear contracts between components
- Excellent IDE support with type hints
- Easy serialization to/from JSON
- Self-documenting code

## Performance Considerations

- **Response Time**: Target < 3 seconds per request
  - Parser: ~10ms (regex-based, very fast)
  - LLM calls: ~2-2.5s (main bottleneck)
  - Total: Typically 2-3 seconds

- **Optimization Opportunities**:
  - Caching for identical error logs
  - Batch processing for multiple errors
  - Using smaller/faster models for simple errors
  - Async processing for multiple requests

## Limitations & Future Improvements

### Current Limitations

1. **Context Dependency**: Fix suggestions depend on having sufficient error context
2. **LLM Variability**: Different runs may produce slightly different classifications
3. **Limited Error Types**: Currently handles 2 base error patterns
4. **No Code Context**: Doesn't have access to actual source code

### Future Improvements

1. **Enhanced Parser**:
   - Support for more error types
   - Better handling of non-standard formats
   - Source code extraction from logs

2. **Smarter Classification**:
   - Fine-tuned models on PLC errors
   - Multi-model ensemble for better accuracy
   - Confidence calibration

3. **Better Fix Suggestions**:
   - Access to project source code
   - Historical fix patterns
   - Interactive debugging

4. **Production Features**:
   - Caching layer (Redis)
   - Rate limiting
   - Monitoring and analytics
   - User feedback loop

## Testing

The project includes comprehensive tests:

- **Unit Tests**: Parser, generator, and individual components
- **Integration Tests**: API endpoints and full pipeline
- **Evaluation Tests**: Automated metrics on synthetic data

## License

[Add your license here]

## Contributors

[Add contributors here]

## Support

For issues or questions, please create an issue in the GitHub repository.
#### POST /classify/stream

Streams the same classification work over Server-Sent Events (SSE). The client receives chunks in this format:

```
data: {"type":"classification","payload":{...}}

data: {"type":"suggestions","payload":[...]}

data: {"type":"parsed_errors","payload":[...]}

data: {"type":"complete","payload":{"status":"ok"}}
```

Use this endpoint for the interactive playground to display data as soon as each section arrives.
### Stream a saved error log

Rather than manually pasting a log into `curl`, you can replay one of the provided samples:

```bash
./scripts/stream_error_log.sh
```

It posts `sample_data/constant_error.txt` directly to `/classify/stream` so you avoid escaping quotes/newlines and can focus on the streamed UI.
