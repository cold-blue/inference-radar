import argparse

from .db import init_db
from .pipeline import collect, analyze, report, run_all


def main():
    parser = argparse.ArgumentParser(
        description="Personal LLM inference technology radar"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db")
    sub.add_parser("collect")
    sub.add_parser("analyze")
    sub.add_parser("report")
    sub.add_parser("run")

    args = parser.parse_args()

    if args.command == "init-db":
        init_db()
        print("Database initialized.")

    elif args.command == "collect":
        print(f"Collected {collect()} new items.")

    elif args.command == "analyze":
        print(f"Analyzed {analyze()} items.")

    elif args.command == "report":
        path = report()
        print(f"Report written to {path}")

    elif args.command == "run":
        run_all()
