from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import logging
import os
import sqlite3
from pathlib import Path

from pyogrio.errors import (
    CRSError,
    DataLayerError,
    DataSourceError,
    FeatureError,
    FieldError,
    GeometryError,
)

from .discovery import discover, write_report
from .model import WfsConfig
from .postgis import PostgisError, PostgisMirror
from .storage import GeoPackagePublisher, StorageError
from .sync import sync_all
from .wfs import WfsClient, WfsError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wfs-sync",
        description="Full sync of eProstor administrative-act WFS layers.",
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv(
            "WFS_ENDPOINT", "https://storitve.eprostor.gov.si/ows-pub-wfs/wfs"
        ),
    )
    parser.add_argument(
        "--page-size", type=int, default=int(os.getenv("WFS_PAGE_SIZE", "5000"))
    )
    parser.add_argument(
        "--timeout", type=float, default=float(os.getenv("WFS_TIMEOUT", "120"))
    )
    parser.add_argument(
        "--retries", type=int, default=int(os.getenv("WFS_RETRIES", "4"))
    )
    parser.add_argument(
        "--log-level", default=os.getenv("WFS_LOG_LEVEL", "INFO")
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="replace both output layers")
    sync_parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.getenv("WFS_OUTPUT", "data/upravni_akti.gpkg")),
    )
    sync_parser.add_argument(
        "--restart",
        action="store_true",
        help="discard an existing partial checkpoint before downloading",
    )

    status_parser = subparsers.add_parser(
        "status", help="show local GeoPackage checkpoint progress without network access"
    )
    status_parser.add_argument(
        "--output",
        type=Path,
        default=Path(os.getenv("WFS_OUTPUT", "data/upravni_akti.gpkg")),
    )

    discover_parser = subparsers.add_parser(
        "discover", help="check schemas/counts without downloading features"
    )
    discover_parser.add_argument(
        "--report",
        type=Path,
        default=Path(os.getenv("WFS_REPORT", "build/wfs-discovery.json")),
    )

    subparsers.add_parser("db-init", help="create and validate the eprostor schema")

    bootstrap_parser = subparsers.add_parser(
        "db-bootstrap", help="seed PostGIS from a completed GeoPackage"
    )
    bootstrap_parser.add_argument("--input", type=Path, required=True)

    db_sync_parser = subparsers.add_parser(
        "db-sync", help="reconcile PostGIS from WFS inventory and changed features"
    )
    db_sync_parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="download every feature instead of only new or changed IDs",
    )
    db_sync_parser.add_argument(
        "--fetch-batch-size",
        type=int,
        default=int(os.getenv("WFS_RESOURCE_BATCH_SIZE", "100")),
    )
    return parser


def _database_url() -> str:
    value = os.getenv("DATABASE_URL")
    if not value:
        raise ValueError("DATABASE_URL is required for PostGIS commands")
    return value


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        logging.basicConfig(
            level=getattr(logging, args.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
        if args.command == "status":
            print(
                json.dumps(
                    asdict(GeoPackagePublisher(args.output).status()),
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            return 0

        if args.command == "db-init":
            PostgisMirror(_database_url()).initialize()
            print(json.dumps({"schema": "eprostor", "initialized": True}))
            return 0

        if args.command == "db-bootstrap":
            results = PostgisMirror(_database_url()).bootstrap(args.input)
            print(
                json.dumps(
                    [asdict(result) for result in results],
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            return 0

        config = WfsConfig(
            base_url=args.endpoint,
            page_size=args.page_size,
            timeout_seconds=args.timeout,
            retries=args.retries,
        )
        client = WfsClient(config)
        if args.command == "discover":
            report = discover(client)
            write_report(report, args.report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if args.command == "db-sync":
            mirror = PostgisMirror(
                _database_url(), fetch_batch_size=args.fetch_batch_size
            )
            results = mirror.sync(client, full_refresh=args.full_refresh)
            print(
                json.dumps(
                    [asdict(result) for result in results],
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            return 0

        publisher = GeoPackagePublisher(args.output)
        results = sync_all(client, publisher, restart=args.restart)
        print(
            json.dumps(
                [
                    {
                        "layer": result.output_name,
                        "features": result.written_count,
                        "bounds": result.bounds,
                    }
                    for result in results
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except (
        WfsError,
        StorageError,
        ValueError,
        OSError,
        sqlite3.Error,
        CRSError,
        DataLayerError,
        DataSourceError,
        FeatureError,
        FieldError,
        GeometryError,
        PostgisError,
    ) as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1
