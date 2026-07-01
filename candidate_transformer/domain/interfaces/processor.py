"""Base processor interface.

Processors form an ordered chain that transforms evidence into a
merged canonical candidate profile.  Each processor reads from and
writes to the :class:`PipelineContext`, which holds the shared
:class:`EvidenceRepository` and intermediate results (candidate
groups, canonical candidates, etc.).

The :attr:`order` property determines execution sequence — lower
values run first.

Processor chain (default order)::

    1. FieldNormaliser       — phones → E.164, dates → YYYY-MM, etc.
    2. SkillCanonicaliser    — alias → canonical skill name
    3. IdentityResolver      — groups evidence by candidate identity
    4. EvidenceMerger        — conflict resolution → CanonicalCandidate
    5. ConfidenceScorer      — per-field + overall confidence
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from candidate_transformer.evidence.repository import EvidenceRepository
    from candidate_transformer.pipeline.context import PipelineContext


class BaseProcessor(ABC):
    """Abstract base class for all pipeline processors.

    Subclasses must set :attr:`name` and :attr:`order` and implement
    :meth:`process`.  The processor registry sorts registered
    processors by :attr:`order` to guarantee a deterministic execution
    sequence.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable processor name for logging and diagnostics."""
        ...

    @property
    @abstractmethod
    def order(self) -> int:
        """Execution order within the processor chain (lower runs first)."""
        ...

    @abstractmethod
    def process(
        self,
        evidence_repo: EvidenceRepository,
        ctx: PipelineContext,
    ) -> None:
        """Execute this processor's transformation.

        Processors read inputs from and write outputs to the
        ``evidence_repo`` and/or ``ctx``.  Convention:

        * Normalisers and canonicalisers update :attr:`Evidence.normalized_value`
          and :attr:`Evidence.confidence` in-place within the repository.
        * The identity resolver stores candidate groups in ``ctx``.
        * The merger reads groups from ``ctx`` and stores
          :class:`CanonicalCandidate` instances in ``ctx``.
        * The confidence scorer updates confidence on the candidates in ``ctx``.

        Parameters
        ----------
        evidence_repo:
            The shared evidence repository containing all extracted evidence.
        ctx:
            The pipeline context carrying configuration, intermediate
            results, and the logger.
        """
        ...
