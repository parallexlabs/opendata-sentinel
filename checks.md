# Check catalogue

Tags are **informative alignments only**. This tool does not certify compliance with ISO, DAMA, DCAT, or any legal framework.

The selected vocabulary is the historical mdq 1.0 XML implementation of [ISO/TS 19157-2:2016](https://www.iso.org/standard/66197.html), derived from ISO 19157:2013. Exact element names follow the [ISO/TC 211 quality-element schema](https://schemas.isotc211.org/19157/-2/mdq/1.0/dataQualityElement.xsd) and [namespace reference](https://schemas.isotc211.org/19157/-2/mdq/1.0/). These are conceptual alignments; the tool does not emit a conforming XML quality report or claim a standardized quality measure.

Missing required values are omission, not commission (excess data). CRS presence and a configured CRS match do not measure positional accuracy. Field age is an operational policy, not temporal reference error. Pattern hits do not establish that personal information exists or that a legal requirement was violated.

DAMA and ISO8000 mappings were removed because the previous terms were not supported by an exact edition and element reference. FIPPA and the unspecified government metadata profile were removed: no legal compliance test is implemented. They are replaced by clearly local operations. The `dct:` properties are metadata vocabulary references from [DCAT 3, W3C Recommendation 22 August 2024](https://www.w3.org/TR/2024/REC-vocab-dcat-3-20240822/); DCAT supplies no row completeness, uniqueness or CRS accuracy metric here.

| Check ID | Informative alignment or local operation |
|---|---|
| `completeness.required_fields` | ISO19157-2:2016:DQ_CompletenessOmission |
| `completeness.geometry_not_null` | ISO19157-2:2016:DQ_CompletenessOmission |
| `validity.type` | ISO19157-2:2016:DQ_FormatConsistency |
| `validity.range` | ISO19157-2:2016:DQ_DomainConsistency |
| `validity.regex` | local:configured_pattern |
| `uniqueness.primary_key` | local:configured_key_uniqueness |
| `timeliness.dataset_modified` | local:metadata_age_policy; dct:modified |
| `timeliness.field_recency` | local:field_age_policy |
| `consistency.cross_field` | ISO19157-2:2016:DQ_ConceptualConsistency |
| `geometry.valid` | ISO19157-2:2016:DQ_TopologicalConsistency |
| `geometry.type_allowed` | local:configured_geometry_type |
| `crs.present` | local:crs_presence |
| `crs.expected` | local:configured_crs_match |
| `domains.allowed_values` | ISO19157-2:2016:DQ_DomainConsistency |
| `metadata.required` | local:required_metadata; dct:title; dct:description; dct:license; dct:modified |
| `privacy.pattern_email_phone` | local:contact_pattern_indicator |
