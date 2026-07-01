# Architecture — Eightfold Multi-Source Candidate Data Transformer

## Why Pipeline?

The candidate transformation process is a natural sequence of discrete, ordered
stages: **extract → normalise → resolve → merge → score → project → validate**.

A pipeline pattern makes this explicit:

- **Determinism**: stages execute in a fixed order so the same inputs always
  produce the same outputs.
- **Testability**: each stage is independently testable with synthetic inputs.
- **Observability**: the pipeline context records timing, warnings, and errors
  per stage, enabling clear diagnostics.
- **Extensibility**: new stages (e.g. a deduplication pass, a data-quality
  audit) slot in by registering a new processor with the appropriate `order`
  value — no changes to existing code.

We considered an event-driven architecture but rejected it because:
- it introduces non-determinism (race conditions, out-of-order events);
- it adds infrastructure complexity (message broker, retry logic) that is
  unjustified at this scale.

---

## Why Evidence?

Every piece of extracted data is wrapped in an `Evidence` object rather than
being passed as a plain dict or tuple.

**Rationale**:

| Concern | How Evidence solves it |
|---------|----------------------|
| **Provenance** | Each Evidence records its `source_type`, `source_ref`, and `extraction_method`, which flow into the output's `provenance` array. |
| **Conflict resolution** | When two sources disagree on a field, the merger compares Evidence objects by source priority, normalisation success, and confidence — not raw strings. |
| **Confidence scoring** | The confidence scorer reads each Evidence's extraction metadata to compute per-field and overall confidence. |
| **Determinism** | Evidence IDs are deterministic SHA-256 hashes of content attributes, so the same input always produces the same internal state. |
| **Testability** | You can construct Evidence objects in unit tests without touching files or APIs. |

We considered storing raw dicts, but:
- dicts have no schema enforcement, making typos (e.g. `"feild_name"`) silent
  bugs;
- dicts lack domain methods like `build_id` and `create`;
- dicts mix concerns (data + metadata) without a clean boundary.

---

## Why Registry?

Both extractors and processors are registered in typed registries
(`ExtractorRegistry`, `ProcessorRegistry`) rather than hard-coded in the
orchestrator.

**Rationale** (Open/Closed Principle):

- **Adding a source**: write a new `BaseExtractor` subclass, register it, done.
  Zero changes to the pipeline orchestrator or any existing extractor.
- **Adding a processor**: write a new `BaseProcessor` subclass with the
  desired `order`, register it. The processor chain adjusts automatically.
- **Testing**: register mock extractors/processors to exercise the pipeline
  without real I/O.

We avoided a plugin/dynamic-discovery system (e.g. entry points, classpath
scanning) because it adds complexity without value at this scale.  Explicit
registration is readable, debuggable, and sufficient.

---

## Why Projection?

The internal `CanonicalCandidate` always carries *every* field.  The
`ProjectionEngine` maps it to the external output shape defined by the runtime
`OutputConfig`.

**Rationale** (Separation of Concerns):

- **Same engine, different outputs**: the default config emits the full schema;
  a custom config can rename fields, select subsets, toggle provenance, or
  remap paths — all without touching the merger or extractors.
- **Stable internal model**: the canonical model never changes shape when a new
  output format is requested.
- **Pure function**: `project(candidate, config) → dict` has no side effects,
  is trivially testable, and is the key enabler of the "configurable output"
  requirement.

We considered generating output directly from the merger, but that would couple
the merger to the output schema, violating SRP and making custom configs
impossible without code changes.

---

## Why Validation?

The validator inspects the projected output before it is emitted and checks
types, required fields, and format constraints.

**Rationale** (Defence in depth):

- **Catch bugs early**: if a normaliser fails silently, the validator catches
  the wrong type or format before the data reaches downstream consumers.
- **Config-driven**: validation rules derive from the `OutputConfig`, so
  custom configs get custom validation automatically.
- **Explicit error reporting**: `ValidationResult` returns structured errors
  rather than crashing, allowing the pipeline to report *all* issues in one
  pass.

---

## Overall Design Decisions

### Clean Architecture

The codebase is organised into concentric rings:

1. **Domain** (innermost): models, interfaces, enums — zero framework
   dependencies beyond Pydantic.
2. **Application**: pipeline orchestrator, config loader, processor/extractor
   registries.
3. **Adapters**: concrete extractors (CSV, JSON, GitHub, Resume), concrete
   processors, projection engine, validator.
4. **Infrastructure** (outermost): CLI, FastAPI endpoint, logging, file I/O.

The dependency rule is enforced: all imports point inward, never outward.

### Dependency Injection

The `PipelineOrchestrator` receives its dependencies (registries, repository,
projection engine, validator) via constructor injection.  This enables:
- mock injection in tests;
- future composition root flexibility (e.g. a different wiring for batch vs.
  real-time).

### Determinism

- Evidence IDs are SHA-256 hashes (not UUIDs).
- Merge resolution uses a deterministic priority ranking (no randomness).
- Processor order is defined by the `order` property (not by registration
  order).
- No threading or async non-determinism in the core pipeline.

### Configuration-Driven Source Priority

Source priority is **not hard-coded**.  The `source_priority` config maps
source-type keys to integer weights:

```json
{
  "source_priority": {
    "ats": 100,
    "resume": 90,
    "github": 80,
    "csv": 70
  }
}
```

The merger reads this at runtime, allowing users to re-rank sources without
code changes.

---

## Trade-offs

| Decision | Benefit | Cost |
|----------|---------|------|
| In-memory EvidenceRepository | Fast, simple, no infrastructure | Not suitable for millions of candidates |
| Pydantic v2 for domain models | Type safety, validation, serialisation | ~5 ms overhead per model; domain couples to pydantic |
| No fuzzy name matching | Deterministic, no false positives | May miss same-person records differing only by name |
| No async pipeline | Simpler, deterministic | Cannot parallelise HTTP calls for GitHub extraction |
| PDF parsing via pdfplumber | Pure Python, no system deps | May struggle with scanned-image PDFs |
| Python stdlib logging | Zero dependencies, universally understood | Less structured than structlog; no auto-context |
