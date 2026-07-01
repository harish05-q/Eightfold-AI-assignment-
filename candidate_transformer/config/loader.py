"""Configuration loader — reads and validates output configuration files.

:class:`ConfigLoader` is the single entry point for obtaining an
:class:`OutputConfig`.  It:

1. Reads a JSON file from disk (or falls back to the bundled default).
2. Validates the structure via Pydantic.
3. Raises :class:`ConfigurationError` eagerly so mis-configurations
   are caught before any data processing begins.
"""

import json
import logging
from pathlib import Path

from candidate_transformer.config.models import OutputConfig
from candidate_transformer.domain.exceptions import ConfigurationError

_DEFAULT_CONFIG_PATH = Path(__file__).parent / "default_output.json"


class ConfigLoader:
    """Loads and validates pipeline output configuration.

    Parameters
    ----------
    logger:
        Optional logger.  Falls back to the ``candidate_transformer.config``
        child logger.
    """

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger(
            "candidate_transformer.config",
        )

    def load(self, path: str | None = None) -> OutputConfig:
        """Load an output configuration.

        Parameters
        ----------
        path:
            Path to a JSON config file.  When ``None``, the bundled
            default configuration is loaded.

        Returns
        -------
        OutputConfig
            Validated output configuration.

        Raises
        ------
        ConfigurationError
            If the file is missing, contains invalid JSON, or fails
            schema validation.
        """
        if path is None:
            return self.load_default()
        return self._load_from_file(Path(path))

    def load_default(self) -> OutputConfig:
        """Load the bundled default output configuration.

        Returns
        -------
        OutputConfig
            The default configuration that emits the full canonical
            schema with standard source priorities.
        """
        self._logger.info("Loading default output configuration")
        return self._load_from_file(_DEFAULT_CONFIG_PATH)

    def load_from_dict(self, raw: dict) -> OutputConfig:
        """Validate and return an OutputConfig from a raw dictionary.

        Useful for programmatic construction (e.g. from FastAPI
        request bodies) without going through a file.

        Parameters
        ----------
        raw:
            Dictionary matching the OutputConfig schema.

        Returns
        -------
        OutputConfig
            Validated configuration.

        Raises
        ------
        ConfigurationError
            If the dictionary fails schema validation.
        """
        return self._validate(raw)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_from_file(self, file_path: Path) -> OutputConfig:
        """Read and validate a JSON config file.

        Raises
        ------
        ConfigurationError
            On file-not-found or JSON parse failure.
        """
        if not file_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {file_path}",
                context={"path": str(file_path)},
            )

        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(
                f"Cannot read configuration file: {file_path}",
                context={"path": str(file_path), "error": str(exc)},
            ) from exc

        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ConfigurationError(
                f"Invalid JSON in configuration file: {file_path}",
                context={"path": str(file_path), "error": str(exc)},
            ) from exc

        if not isinstance(raw, dict):
            raise ConfigurationError(
                f"Configuration must be a JSON object, got {type(raw).__name__}",
                context={"path": str(file_path)},
            )

        self._logger.info(
            "Loaded configuration from %s",
            file_path,
        )
        return self._validate(raw)

    def _validate(self, raw: dict) -> OutputConfig:
        """Validate a raw dict against the OutputConfig schema.

        Raises
        ------
        ConfigurationError
            On validation failure, wrapping the original Pydantic error.
        """
        try:
            config = OutputConfig.model_validate(raw)
        except Exception as exc:
            raise ConfigurationError(
                f"Invalid configuration structure: {exc}",
                context={"error": str(exc)},
            ) from exc

        self._logger.info(
            "Config validated: %d field specs, on_missing=%s, "
            "priorities=%s",
            len(config.fields),
            config.on_missing.value,
            config.source_priority,
        )
        return config
