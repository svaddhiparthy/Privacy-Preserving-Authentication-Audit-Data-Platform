import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from pramanaledger.sources import write_normalized_sample


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize the RBA Kaggle/Zenodo dataset into Privacy-Preserving Authentication Audit Data Platform login events.")
    parser.add_argument("--source", required=True, help="Path to rba-dataset zip or CSV.")
    parser.add_argument("--output", default="data/external/rba/login_events.normalized.jsonl")
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args()

    count = write_normalized_sample(Path(args.source), Path(args.output), limit=args.limit)
    print(f"Normalized {count} RBA rows into {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
