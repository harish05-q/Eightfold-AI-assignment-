# Candidate Transformer Pipeline

## 🎥 Demo Video Link
[Link to Demo Video] *(Replace with actual link)*

A deterministic, configuration-driven pipeline for unifying unstructured candidate data across disparate sources (ATS, Recruiter CSVs, GitHub, Resumes). Built with Python 3.12, Clean Architecture, and SOLID principles.

## Features

- **Multi-Source Extraction**: Seamlessly extracts profiles from CSV, ATS exports, GitHub APIs, and Resumes.
- **Deterministic Identity Resolution**: Deterministically merges candidate profiles based on a strict priority chain (`Email -> Phone -> Name`) utilizing a graph-based connected component merging algorithm.
- **Config-Driven Output**: Map internal canonical structures directly into dynamic JSON shapes using the `OutputConfig`.
- **Explainability**: Rich logging and `PipelineContext` tracking ensures that every piece of evidence, every error, and every processing time metric is recorded and auditable.
- **Defensive Boundaries**: Uses Pydantic to ensure models remain intact. Strict validation against configurations ensures consumers get exactly what they expect.

---

## 🚀 Exact Run Steps

### 1. Installation
Ensure you have Python 3.12+ installed.
```bash
# Clone the repository
git clone <your-repo-url>
cd <repo-directory>

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the End-to-End Pipeline (CLI)
We have pre-configured a manifest that processes 4 distinct sources (ATS, Recruiter CSV, GitHub, Resume) belonging to a single fragmented identity ("Alice Engineer").

Run the pipeline:
```bash
python main.py sample_inputs/manifest.json -o sample_outputs/default_output.json
```

**Running with Custom Config:**
```bash
python main.py sample_inputs/manifest.json -c sample_inputs/custom_config.json -o sample_outputs/custom_output.json
```

### 3. Run the FastAPI Endpoints
The application exposes a thin FastAPI wrapper to run the pipeline dynamically.
```bash
# Start the server
uvicorn candidate_transformer.api:app --reload
```
Open another terminal and use `curl` to submit the manifest:
```bash
curl -X POST "http://127.0.0.1:8000/transform" \
     -H "Content-Type: application/json" \
     -d @sample_inputs/manifest.json
```

---

## 📄 Produced Output

After running the CLI command, the system deterministically resolves the 4 fragmented inputs into a single canonical candidate and maps it to the default JSON shape. 

*Snippet of `sample_outputs/default_output.json`:*
```json
{
  "run_id": "e962ad91-e3a5-4d7f-91c9-5dc7d26e2e3e",
  "timing": {
    "total": 0.108
  },
  "warnings": [],
  "errors": [],
  "candidates": [
    {
      "candidate_id": "cand_a76b702576d5",
      "full_name": "Alice B. Engineer",
      "emails": [
        "alice.eng@email.com",
        "alice@example.com"
      ],
      "phones": [
        "5551234567",
        "+15551234567"
      ],
      "location": {
        "city": "San Francisco",
        "region": "CA",
        "country": "CA"
      },
      "skills": [
        {
          "name": "Go",
          "confidence": 0.8,
          "sources": ["ats"]
        },
        {
          "name": "Python",
          "confidence": 0.75,
          "sources": ["ats", "resume"]
        }
      ]
    }
  ]
}
```

---

## 🧪 Tests

The pipeline ships with **149 robust tests** providing 100% verification across isolated layers, error handling, and cross-source identity resolution edge cases.

To run the test suite:
```bash
pytest tests/ -v
```

*Expected Output snippet:*
```
============================= test session starts =============================
...
tests/unit/test_orchestrator.py::TestPipelineOrchestrator::test_run_success_flow PASSED
tests/unit/test_validator.py::TestConfigValidator::test_type_checking PASSED
tests/integration/test_pipeline_e2e.py::test_pipeline_e2e_with_sample_data PASSED
...
============================= 149 passed in 1.45s =============================
```

---

## 🧠 Assumptions & Design Decisions

1. **Identity Resolution**: We assumed a strict deterministic approach. Fuzzy matching was explicitly descoped. Identity merging relies strictly on Connected Components Graph logic via exact E.164 phone matches or exact email matches.
2. **Missing Field Policies**: If a source is missing a required field configured in `OutputConfig`, we assume the pipeline should gracefully warn and omit the field (or candidate) based on the policy, rather than crash.
3. **Data Precedence**: It is assumed that certain systems have higher trust. Source priorities were config-driven (e.g., ATS=100, Resume=90, GitHub=80, CSV=70) to resolve conflicting scalar fields like names.
4. **Resumes Parsing**: Text resumes are assumed to be semi-structured. We used basic RegEx extractors for the demo rather than importing heavy NLP models (like spaCy) to keep dependencies light and focus on the architecture.

---

## ❌ Descoped Items

1. **Fuzzy Name Matching**: Advanced Levenshtein distance or ML-based identity matching is descoped. 
2. **PDF OCR Processing**: Parsing PDFs that are strictly images (non-selectable text) was descoped. The `resume_extractor` currently mocks the PDF binary extraction layer.
3. **Authentication/Security**: The FastAPI endpoints do not include JWT or OAuth flows.
4. **Database Persistence**: The `EvidenceRepository` is in-memory. Connecting to PostgreSQL or MongoDB was descoped to keep the pipeline easily runnable on any local machine.

---

## Project Structure

```
├── candidate_transformer/
│   ├── config/              # Configuration models (OutputConfig, FieldSpec)
│   ├── domain/              # Core business logic models, enums, interfaces, exceptions
│   ├── evidence/            # Evidence Repository (in-memory store)
│   ├── extractors/          # Extractors (CSV, ATS JSON, GitHub, Resumes)
│   ├── pipeline/            # Orchestrator and Context state management
│   ├── processors/          # Processors (Normalizer, Canonicalizer, Resolver, Merger, Scorer)
│   ├── projection/          # Projection Engine (mapping to output schema)
│   └── validation/          # Validation Layer
├── resources/               # Static resources (skill aliases)
├── sample_inputs/           # Sample inputs for testing
├── sample_outputs/          # Sample outputs generated by the pipeline
├── tests/                   # Extensive test suite (149 passing tests)
├── main.py                  # CLI Entry point
└── README.md
```

## Architecture

Please refer to `docs/ARCHITECTURE.md` for a complete breakdown of the layers, data flows, boundaries, and decisions.
