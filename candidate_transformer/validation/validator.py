"""Config-driven Validation layer.

Validates the final projected output dictionaries against the
OutputConfig field specifications.
"""

from candidate_transformer.config.models import OutputConfig, FieldSpec
from candidate_transformer.domain.interfaces.validator import BaseValidator, ValidationResult


class ConfigValidator(BaseValidator):
    """Validates projected data against an OutputConfig."""

    def validate(self, data: dict[str, object], config: OutputConfig) -> ValidationResult:
        """Inspect data against config rules and return a ValidationResult."""
        errors: list[str] = []
        warnings: list[str] = []

        fields_to_validate = config.fields
        if not fields_to_validate:
            # Reconstruct default fields based on the canonical schema shape
            fields_to_validate = [
                FieldSpec(path="candidate_id", type="string", required=True),
                FieldSpec(path="full_name", type="string"),
                FieldSpec(path="emails", type="string[]"),
                FieldSpec(path="phones", type="string[]"),
                FieldSpec(path="location", type="object"),
                FieldSpec(path="links", type="object"),
                FieldSpec(path="headline", type="string"),
                FieldSpec(path="years_experience", type="number"),
                FieldSpec(path="skills", type="object[]"),
                FieldSpec(path="experience", type="object[]"),
                FieldSpec(path="education", type="object[]"),
                FieldSpec(path="provenance", type="object[]"),
            ]
            if config.include_confidence:
                fields_to_validate.append(FieldSpec(path="overall_confidence", type="number"))

        for spec in fields_to_validate:
            val = data.get(spec.path)

            if val is None:
                if spec.required:
                    errors.append(f"Missing required field: '{spec.path}'")
                # If it's missing but not required, we skip type checking.
                # (The projection engine respects MissingPolicy, so if it's here as None
                # or missing, it's allowed by the policy).
                continue

            # Type checking
            expected_type = spec.type
            if expected_type == "string" and not isinstance(val, str):
                errors.append(f"Field '{spec.path}' expected string, got {type(val).__name__}")
            elif expected_type == "number" and not isinstance(val, (int, float)):
                errors.append(f"Field '{spec.path}' expected number, got {type(val).__name__}")
            elif expected_type == "object" and not isinstance(val, dict):
                errors.append(f"Field '{spec.path}' expected object, got {type(val).__name__}")
            elif expected_type == "string[]":
                if not isinstance(val, list):
                    errors.append(f"Field '{spec.path}' expected string[], got {type(val).__name__}")
                elif any(not isinstance(item, str) for item in val):
                    errors.append(f"Field '{spec.path}' expected string[], but list contains non-string items")
            elif expected_type == "object[]":
                if not isinstance(val, list):
                    errors.append(f"Field '{spec.path}' expected object[], got {type(val).__name__}")
                elif any(not isinstance(item, dict) for item in val):
                    errors.append(f"Field '{spec.path}' expected object[], but list contains non-object items")
            elif expected_type not in ("string", "number", "object", "string[]", "object[]"):
                # Unknown type specification
                warnings.append(f"Unknown type '{expected_type}' specified for field '{spec.path}'. Type check skipped.")

        # Check for extraneous fields (fields in output not defined in config)
        allowed_paths = {spec.path for spec in fields_to_validate}
        for key in data.keys():
            if key not in allowed_paths:
                warnings.append(f"Extraneous field found in output: '{key}'")

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
