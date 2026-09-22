$ErrorActionPreference = "Stop"

# Mirrors the lint and test jobs in .github/workflows/ci.yml.
ruff check .
pytest
python scripts/check_test_count.py

Write-Host "Smoke test passed."
