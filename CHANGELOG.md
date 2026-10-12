# Changelog

## Corrections - 2026-10-01

Corrected the connector label. Added guarded redirects and capped retry waits. Recorded the bootstrap seeds. Marked automatic findings as not reviewed for actionability. Current results are in RESULTS.md.

Public data provenance and terms: [Vancouver catalogue](https://opendata.vancouver.ca/), [Open Government Licence - Vancouver](https://opendata.vancouver.ca/pages/licence/). Existing multi-source capabilities are credited in `docs/technical-report.md`, with primary sources.

## 0.4.0 - 2026-09-30

### Benchmark integrity (phase 3)

- Fix injected-defect precision: unmatched findings count as false positives; each defect injected in isolation with five instances.
- Add same-dataset schema drift detection (`same_dataset_schema_drift`); value drift joins on `geo_point_2d`, not `name`.
- Report uninjected synthetic-marker matches (not municipal false-positive rate); omit real-data recall for provisional labels.
- Historical merge behaviour was superseded: current internal/Frictionless reports are retained separately.
- Measure peak memory in per-mode subprocess probes.
- Add `docs/PREREGISTRATION_AMENDMENT_2026-09-30.md`; add dbt tests, Soda, and Kubler DOI to prior-art tables.
- One-command regeneration: `bash scripts/regenerate_all.sh`.

## 0.3.0 - 2026-09-30

### Benchmark

- Add versioned cross-dataset consistency benchmark on City of Vancouver open data.
- CLI: `civic-data-qa benchmark info` and `civic-data-qa benchmark run`.
- Relation checks: referential, cross-field, and snapshot drift with confidence-ranked findings.
- Historical schema comparison: only internal plus Frictionless passes executed; other tools were not benchmarked.
- Historical provisional label evaluation; current real-data recall is omitted and actionability is unverified.

## 0.2.0 - 2026-09-28

### Security

- Validate outbound URLs (HTTPS by default; HTTP only with explicit opt-in), reject private/reserved IPs in DNS validation, and restrict CKAN resource downloads to the catalogue host.
- Disable cross-origin redirects; strip Authorization headers on redirect hops.
- Stop forwarding CKAN API credentials to resource download hosts.

### Behaviour changes

- Unknown remote hosts are rejected instead of defaulting to the OpenDataSoft adapter. Set `CIVIC_DATA_QA_ALLOW_ARBITRARY_URLS=1` to opt in to treating unrecognized HTTPS URLs as OpenDataSoft Explore v2.1 endpoints.
- Geometry validity checks run automatically whenever the loaded dataset contains geometry, not only when geometry is configured.
- Null geometries are excluded from validity/type checks; empty geometries count as invalid.
- Timeliness checks normalise dates to UTC and report missing or unparsable field dates.
- Configuration uses strict validation (`extra=forbid`); unknown keys, invalid plugin names, and inverted range bounds are rejected.
- CRS comparison uses pyproj semantic equivalence instead of string matching.
- HTTP client honours `Retry-After` with bounded exponential backoff for 429 and 5xx responses.

### Accessibility

- HTML reports include a `<main>` landmark, skip link, and `.visually-hidden` utility class.

### Documentation

- Standards mappings rewritten as informative alignments with precise DCAT property identifiers (`dct:title`, `dct:description`, `dct:license`, `dct:modified`).

## 0.1.0 - 2026-09-28

Initial release.
