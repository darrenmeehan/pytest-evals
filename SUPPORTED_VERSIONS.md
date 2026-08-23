# Supported versions

Last reviewed: 2026-08-23

## Python

| Version | Status | EOL | Notes |
|---------|--------|-----|-------|
| 3.10 | supported | 2026-10 | Minimum required by `requires-python` |
| 3.11 | supported | 2027-10 | |
| 3.12 | supported | 2028-10 | |
| 3.13 | supported | 2029-10 | |
| 3.14 | supported | 2031-10 | |
| 3.15 | pre-release | 2032-10 | Tested via CI `allow-prereleases` |

## pytest

| Version | Status | Min Python | Release date |
|---------|--------|------------|--------------|
| 9.0+ | supported | 3.10 | 2025-11-05 |
| 8.4 | unsupported | 3.9 | 2025-06-02 |
| <8.4 | unsupported | — | — |

## CI actions

| Action | Version | Published | Notes |
|--------|---------|-----------|-------|
| `actions/checkout` | v7.0.1 | 2026-07-17 | |
| `actions/setup-python` | v7.0.0 | 2026-07-20 | node24 runtime |
| `astral-sh/setup-uv` | v10.0.1 | 2026-08-14 | |

## Updating this file

Run this to review active statuses:

```bash
# Python status: https://devguide.python.org/versions/
# pytest status: https://docs.pytest.org/en/stable/backwards-compatibility.html
# CI action releases: check GitHub release pages
```

Bump the "Last reviewed" date and update any changed rows.