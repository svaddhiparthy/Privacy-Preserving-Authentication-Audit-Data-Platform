$ErrorActionPreference = "Stop"

python -m unittest discover -s tests -p "test_*.py"
Get-ChildItem src\pramanaledger\*.py | ForEach-Object { python -m py_compile $_.FullName }
python -m py_compile code_fetch_vaddhiparthy.py demo_api.py

Write-Host "Smoke test passed."
