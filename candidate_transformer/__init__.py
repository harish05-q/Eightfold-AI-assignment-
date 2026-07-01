"""Candidate Transformer — Multi-source candidate data transformation pipeline.

Ingests candidate information from structured (CSV, ATS JSON) and unstructured
(Resume PDF/TXT, GitHub) sources, merges them into a single canonical profile
with provenance tracking and confidence scoring, and projects the result into
a configurable output schema.
"""

__version__ = "1.0.0"
