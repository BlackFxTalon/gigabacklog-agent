from __future__ import annotations

import argparse
from pathlib import Path

from gigabacklog_agent.database import SQLiteRunStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset the local GigaBacklog demonstration database."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        required=True,
        help="Recreate the database, including seed history and run records.",
    )
    parser.add_argument("--database", type=Path, default=Path("data") / "prototype.db")
    arguments = parser.parse_args()
    SQLiteRunStore(arguments.database).reset()
    print(f"Database reset: {arguments.database}")


if __name__ == "__main__":
    main()
