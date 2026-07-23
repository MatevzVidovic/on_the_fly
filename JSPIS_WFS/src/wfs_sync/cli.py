from __future__ import annotations

import argparse
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

    discover_parser = subparsers.add_parser(
        "discover", help="check schemas/counts without downloading features"
    )
    discover_parser.add_argument(
        "--report",
        type=Path,
        default=Path(os.getenv("WFS_REPORT", "build/wfs-discovery.json")),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        logging.basicConfig(
            level=getattr(logging, args.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
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
        results = sync_all(client, GeoPackagePublisher(args.output))
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
    ) as exc:
        logging.getLogger(__name__).error("%s", exc)
        return 1
