"""Regenerate the deterministic data used by the GitHub Pages cost lab."""

from __future__ import annotations

import argparse
from pathlib import Path

from agentflow.site_data import write_site_data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("site/data.json"))
    args = parser.parse_args()
    write_site_data(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
