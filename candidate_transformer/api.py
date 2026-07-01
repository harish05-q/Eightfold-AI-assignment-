"""FastAPI thin wrapper for the Candidate Transformer pipeline."""

import logging
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from candidate_transformer.config.models import OutputConfig
from candidate_transformer.domain.models.input import InputManifest
from candidate_transformer.factory import create_standard_orchestrator

logger = logging.getLogger("candidate_transformer.api")

app = FastAPI(
    title="Candidate Transformer API",
    description="Deterministic pipeline for unifying unstructured candidate data.",
    version="1.0.0",
)


class TransformRequest(BaseModel):
    """Payload for the transform endpoint."""
    manifest: InputManifest
    config: OutputConfig = Field(default_factory=OutputConfig)


class TransformResponse(BaseModel):
    """Response payload for the transform endpoint."""
    run_id: str
    candidates: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    warnings: list[str]
    timing: dict[str, float]


@app.post("/transform", response_model=TransformResponse)
def transform_candidates(request: TransformRequest) -> TransformResponse:
    """Execute the pipeline on a given manifest."""
    logger.info("Received transform request with %d sources.", len(request.manifest.sources))
    
    try:
        orchestrator = create_standard_orchestrator()
        result = orchestrator.run(request.manifest, request.config)
        
        # Serialize errors for JSON response
        serializable_errors = [
            {
                "stage": err.stage,
                "source": err.source,
                "error_type": err.error_type,
                "message": err.message,
                "timestamp": err.timestamp.isoformat()
            }
            for err in result.errors
        ]
        
        return TransformResponse(
            run_id=result.run_id,
            candidates=result.candidates,
            errors=serializable_errors,
            warnings=result.warnings,
            timing=result.timing,
        )
    except Exception as e:
        logger.exception("Pipeline crashed unexpectedly.")
        raise HTTPException(status_code=500, detail=str(e))
