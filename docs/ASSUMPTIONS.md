# Assumptions

This document lists every assumption made by the candidate transformer system.
Each assumption is stated explicitly so that reviewers and future maintainers
understand the boundaries of the current implementation.

---

## Identity Resolution

1. **Email is the primary identity key.**  If two source records share the same
   email address (case-insensitive), they are assumed to represent the same
   candidate.

2. **Phone (after E.164 normalisation) is the secondary identity key.**  If
   emails are absent or non-overlapping, matching E.164 phone numbers identify
   the same candidate.

3. **Exact normalised full name is the tertiary identity key.**  Name matching
   is case-insensitive and whitespace-normalised, but *not* fuzzy.  "John Doe"
   and "john doe" match; "Jon Doe" and "John Doe" do **not**.

4. **Fuzzy name matching is not implemented.**  It is documented as a future
   enhancement.  The current system may produce duplicate profiles for the same
   person if they appear with different names and no overlapping email/phone.

---

## Data Handling

5. **Missing values are never invented.**  If a source does not provide a
   value, the corresponding field in the canonical profile is `null`.  The
   system never guesses or infers data that is not explicitly present.

6. **Wrong-but-confident is worse than honestly-empty.**  The merger prefers
   `null` over a low-confidence value when no source provides a reliable signal.

7. **All text is UTF-8.**  The system assumes all input files and API responses
   are encoded in UTF-8.  Non-UTF-8 inputs will be handled with replacement
   characters rather than crashing.

8. **Phone numbers are assumed to be US (+1) when no country code is
   provided.**  The `phonenumbers` library requires a default region; US is
   chosen as the default because sample data is US-centric.  This default is
   configurable.

9. **Dates are normalised to YYYY-MM.**  Year-only dates (e.g. "2020") become
   `"2020-01"` with lower confidence.  Dates that cannot be parsed at all
   become `null`.

10. **Skill names are canonicalised via a static alias mapping.**  The mapping
    (`resources/skill_aliases.json`) is finite and hand-curated.  Skills not in
    the mapping pass through with their original casing preserved.

---

## Resume Parsing

11. **The first non-empty line of a plain-text resume is assumed to be the
    candidate's full name.**  This heuristic is simple but covers the vast
    majority of real-world resume formats.

12. **Email and phone are extracted from resume text via regex patterns.**
    The regex may miss unusual formats but will not produce false positives for
    standard email/phone patterns.

13. **PDF resume parsing relies on pdfplumber.**  Scanned-image PDFs (without
    embedded text) will produce no extracted data, and the pipeline will
    gracefully degrade.

---

## GitHub Extraction

14. **GitHub data may be a cached JSON file or a live API response.**  If the
    input path ends with `.json`, it is read as a cached file.  Otherwise, it
    is treated as a GitHub profile URL and fetched via the public REST API.

15. **GitHub profile fields (name, bio, location, blog) are extracted as-is.**
    Repository languages are aggregated to infer skills.

16. **GitHub API rate limiting is handled gracefully.**  If the API returns a
    429 or 403, the extractor logs a warning and returns no evidence rather
    than crashing.

---

## Source Priority and Merge

17. **Source priority is configuration-driven, not hard-coded.**  Defaults:
    ATS (100) > Resume (90) > GitHub (80) > CSV (70).

18. **For scalar fields (name, headline, etc.), the highest-priority source
    wins.**  Ties are broken by confidence score.

19. **For list fields (emails, phones, skills), values are unioned and
    deduplicated.**  All unique values are kept regardless of source priority.

20. **The provenance record always reflects the winning source.**  Even when
    multiple sources agree, provenance records the single source that
    contributed the value.

---

## Output and Validation

21. **The default output schema matches the assignment specification exactly.**
    Custom output configs may select, rename, or remap fields but cannot
    introduce new fields that do not exist in the canonical model.

22. **`on_missing: "error"` causes a validation error, not a pipeline
    crash.**  The pipeline still produces output but marks the result as
    invalid via `ValidationResult`.

23. **Country values are normalised to ISO-3166 alpha-2 codes.**  The system
    attempts to resolve country names (e.g. "United States" → "US") and falls
    back to `null` for unrecognisable values.

---

## Scope Boundaries

24. **LinkedIn extraction is not implemented.**  Web scraping raises legal
    concerns; a LinkedIn extractor is architecturally supported but not
    shipped.

25. **Recruiter notes (free-text TXT) extraction is not implemented.**
    Reliable information extraction from free text requires NLP, which is out
    of scope.

26. **The pipeline runs single-threaded.**  Parallelism is a future
    enhancement.  The current design handles thousands of candidates in
    reasonable time without it.

27. **The EvidenceRepository is in-memory.**  For the target scale (thousands
    of candidates per run), an in-memory store is sufficient.  Swapping to a
    database is a future enhancement enabled by the narrow repository
    interface.
