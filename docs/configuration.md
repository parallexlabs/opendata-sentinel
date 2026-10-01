# Configuration

Rulesets are YAML files with `dataset` and `checks` sections.

```yaml
dataset:
  id: my-dataset
  primary_key: id
  expected_crs: EPSG:4326

checks:
  completeness:
    required: [id, name]
  validity:
    types:
      id: integer
    ranges:
      amount:
        min: 0
  uniqueness:
    primary_key: id
  timeliness:
    maximum_age_days: 365
  privacy:
    enabled: true
  metadata:
    required: [title, licence]
```

Invalid YAML or schema fields produce a non-zero exit with a field path error.
