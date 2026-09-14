"""Fail if the test count published on the page has drifted from the actual suite.

The project page states how many tests gate every push. That claim has to stay true without
anyone remembering to update it, so CI asserts it.

Usage:
    python scripts/check_test_count.py           # verify
    python scripts/check_test_count.py --write   # update TEST_COUNT to the real value
"""

import argparse
import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_FILE = PROJECT_ROOT / "src" / "authaudit" / "api.py"
PATTERN = re.compile(r"^TEST_COUNT = (\d+)$", re.MULTILINE)


class _Counter:
    """Collect-only plugin that records how many tests pytest found."""

    def __init__(self) -> None:
        self.count = 0

    def pytest_collection_modifyitems(self, items) -> None:
        self.count = len(items)


def collected_test_count() -> int:
    counter = _Counter()
    status = pytest.main(
        [
            "--collect-only",
            "-q",
            "--no-header",
            "-p",
            "no:cacheprovider",
            str(PROJECT_ROOT / "tests"),
        ],
        plugins=[counter],
    )
    if status != 0:
        sys.exit(f"pytest collection failed with status {status}")
    if counter.count == 0:
        sys.exit("collected zero tests, refusing to report a count")
    return counter.count


def declared_test_count(source: str) -> int:
    match = PATTERN.search(source)
    if not match:
        sys.exit(f"TEST_COUNT not found in {API_FILE}")
    return int(match.group(1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="update TEST_COUNT in place")
    args = parser.parse_args()

    actual = collected_test_count()
    source = API_FILE.read_text(encoding="utf-8")
    declared = declared_test_count(source)

    if declared == actual:
        print(f"test count is accurate: {actual}")
        return

    if args.write:
        API_FILE.write_text(
            PATTERN.sub(f"TEST_COUNT = {actual}", source, count=1), encoding="utf-8"
        )
        print(f"TEST_COUNT updated: {declared} -> {actual}")
        return

    sys.exit(
        f"the page claims {declared} tests but the suite has {actual}.\n"
        f"Run: python scripts/check_test_count.py --write"
    )


if __name__ == "__main__":
    main()
