"""Informative alignments; XML element names follow ISO/TS 19157-2:2016 mdq 1.0.

Source: https://schemas.isotc211.org/19157/-2/mdq/1.0/dataQualityElement.xsd
Metadata properties: https://www.w3.org/TR/vocab-dcat-3/
Local tags describe operations without asserting a standards or legal mapping.
"""

from __future__ import annotations

STANDARDS_TAGS: dict[str, list[str]] = {
    "completeness.required_fields": ["ISO19157-2:2016:DQ_CompletenessOmission"],
    "completeness.geometry_not_null": ["ISO19157-2:2016:DQ_CompletenessOmission"],
    "validity.type": ["ISO19157-2:2016:DQ_FormatConsistency"],
    "validity.range": ["ISO19157-2:2016:DQ_DomainConsistency"],
    "validity.regex": ["local:configured_pattern"],
    "uniqueness.primary_key": ["local:configured_key_uniqueness"],
    "timeliness.dataset_modified": ["local:metadata_age_policy", "dct:modified"],
    "timeliness.field_recency": ["local:field_age_policy"],
    "consistency.cross_field": ["ISO19157-2:2016:DQ_ConceptualConsistency"],
    "geometry.valid": ["ISO19157-2:2016:DQ_TopologicalConsistency"],
    "geometry.type_allowed": ["local:configured_geometry_type"],
    "crs.present": ["local:crs_presence"],
    "crs.expected": ["local:configured_crs_match"],
    "domains.allowed_values": ["ISO19157-2:2016:DQ_DomainConsistency"],
    "metadata.required": ["local:required_metadata", "dct:title", "dct:description", "dct:license", "dct:modified"],
    "privacy.pattern_email_phone": ["local:contact_pattern_indicator"],
}

NON_CERTIFICATION = (
    "Standards tags are informative alignments only. "
    "This tool does not certify compliance with ISO, DAMA, DCAT, or any legal framework."
)


def tags_for(check_id: str) -> list[str]:
    return list(STANDARDS_TAGS.get(check_id, ["UNMAPPED"]))
