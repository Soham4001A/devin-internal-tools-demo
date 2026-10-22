"""CLI: python -m app.seed [--tool refunds]  — resets that tool to synthetic fixtures."""
import argparse

from . import db
from .tools import TOOLS

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default="all", choices=["all", *TOOLS])
    a = ap.parse_args()
    for key in (TOOLS if a.tool == "all" else [a.tool]):
        db.reset_tool(key)
        print(f"Reset {key} -> {db.db_path()}")
