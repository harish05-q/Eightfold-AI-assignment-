"""Logging setup using Python's standard logging module.

Configures a single ``candidate_transformer`` logger that writes to
stderr with a human-readable format.  Child loggers (e.g.
``candidate_transformer.extractors.csv``) inherit this configuration
automatically via Python's logger hierarchy.

The setup function is idempotent — calling it multiple times returns
the same logger without adding duplicate handlers.
"""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure and return the root ``candidate_transformer`` logger.

    Parameters
    ----------
    level:
        Minimum log level (default ``INFO``).

    Returns
    -------
    logging.Logger
        Configured logger ready for use.  Pass it to
        :class:`PipelineContext` or use ``logging.getLogger(__name__)``
        in individual modules.
    """
    logger = logging.getLogger("candidate_transformer")

    # Idempotent: skip if already configured
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)

    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
