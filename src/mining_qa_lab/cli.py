from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from .errors import ConfigError
from .config import ConfigStore, write_example
from .database import OrchestratorDatabase
from .engine import OrchestratorEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="miner-orchestrator",
        description="Watch repositories and schedule mining hardware test gates.",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get("MINER_ORCHESTRATOR_CONFIG", "orchestrator.yaml"),
        help="orchestrator YAML path (default: orchestrator.yaml)",
    )
    parser.add_argument("--verbose", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="validate configuration and print its digest")
    init = commands.add_parser("init-config", help="copy the example configuration")
    init.add_argument("path", nargs="?", default="orchestrator.yaml")
    commands.add_parser("serve", help="run the REST API, web UI, watchers, and queue")
    commands.add_parser("poll-once", help="poll sources and plan newly observed events")
    central = commands.add_parser(
        "central-once",
        help="announce, pull, and process one bounded central coordination page",
    )
    central.add_argument(
        "--phase",
        choices=("run", "claim-only", "reclaim"),
        default="run",
        help="integration recovery phase (loopback-only except run)",
    )
    central_agent = commands.add_parser(
        "central-agent",
        help="run the continuous central coordination agent with bounded backoff",
    )
    central_agent.add_argument(
        "--max-cycles",
        type=int,
        help="stop after this many cycles (intended for validation)",
    )
    register = commands.add_parser(
        "central-register",
        help="bind an app-issued Lab token and create a private environment file",
    )
    register.add_argument("--public-label", required=True)
    register.add_argument("--agent-environment-file", required=True, type=Path)
    central.add_argument(
        "--replay-from-zero",
        action="store_true",
        help="replay the bounded work feed to validate duplicate suppression (loopback-only)",
    )
    run = commands.add_parser("run", help="queue a manual gate run")
    run.add_argument("gate_id")
    run.add_argument("commit_sha")
    run.add_argument("--branch")
    run.add_argument("--wait", action="store_true", help="execute until this run completes")
    return parser


def _database(store: ConfigStore) -> OrchestratorDatabase:
    controller = store.snapshot.document["controller"]
    state_dir = Path(controller["state_dir"])
    if not state_dir.is_absolute():
        state_dir = (store.source.parent / state_dir).resolve()
    return OrchestratorDatabase(state_dir / "orchestrator.sqlite3")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        if args.command == "init-config":
            destination = write_example(args.path)
            print(destination)
            return 0
        store = ConfigStore(args.config)
        if args.command == "validate":
            print(store.snapshot.revision)
            return 0
        if args.command == "central-register":
            from .central import register_central_lab

            result = register_central_lab(
                store,
                public_label=args.public_label,
                agent_environment_file=args.agent_environment_file,
            )
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        database = _database(store)
        if args.command == "central-once":
            from .central import run_central_once

            outcomes = run_central_once(
                store,
                database,
                phase=args.phase,
                replay_from_zero=args.replay_from_zero,
            )
            print(json.dumps({"outcomes": outcomes}, sort_keys=True))
            return 0
        if args.command == "central-agent":
            from .central import run_central_forever

            if args.max_cycles is not None and args.max_cycles < 1:
                raise ConfigError("--max-cycles must be positive")
            cycles = run_central_forever(
                store,
                database,
                max_cycles=args.max_cycles,
            )
            print(json.dumps({"cycles": cycles}, sort_keys=True))
            return 0
        engine = OrchestratorEngine(store, database)
        if args.command == "poll-once":
            created = engine.poll()
            print(json.dumps({"created": created}, sort_keys=True))
            return 0
        if args.command == "run":
            run = engine.manual_run(args.gate_id, args.commit_sha, args.branch)
            if args.wait:
                while database.gate_run(run["id"])["status"] in {"queued", "running"}:
                    if not engine.tick():
                        time.sleep(0.25)
                run = database.gate_run(run["id"])
            print(json.dumps(run, indent=2, sort_keys=True))
            return 0 if run["status"] not in {"failed", "error"} else 1
        if args.command == "serve":
            try:
                import uvicorn
            except ImportError as exc:
                raise ConfigError(
                    "serve requires service dependencies: pip install -e ."
                ) from exc
            from .web import api_token, create_app

            controller = store.snapshot.document["controller"]
            if controller.get("auth_mode", "bearer") == "bearer":
                token_path = Path(controller["state_dir"])
                if not token_path.is_absolute():
                    token_path = (store.source.parent / token_path).resolve()
                token_path /= "api-token"
                api_token(store)
                logging.getLogger(__name__).info("local API token: %s", token_path)
            else:
                logging.getLogger(__name__).warning(
                    "API authentication disabled; allowed client networks: %s",
                    ", ".join(controller["allowed_networks"]),
                )
            uvicorn.run(
                create_app(store, database, engine),
                host=str(controller["bind"]),
                port=int(controller["port"]),
                log_level="debug" if args.verbose else "info",
            )
            return 0
        raise AssertionError(args.command)
    except (ConfigError, OSError) as exc:
        print(f"miner-orchestrator: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
