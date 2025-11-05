"""Command line interface for ingesting champion data."""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Tuple

from .database import ChampionDatabase
from .hellhades import extract_champions
from .parser import parse_champion, slugify

USER_AGENT = "Mozilla/5.0 (compatible; InteleriaScraper/1.0)"


def fetch_url(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # type: ignore[call-arg]
        encoding = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(encoding, errors="ignore")


def ingest_source(db: ChampionDatabase, html: str, slug: Optional[str] = None) -> None:
    data = parse_champion(html, slug=slug)
    db.upsert_champion(data)


def download_pages(
    slugs: Iterable[str],
    loader: Callable[[str], str],
    output_dir: Path,
    *,
    progress: Optional[Callable[[str, bool, Optional[str]], None]] = None,
) -> List[Path]:
    """Download champion pages to ``output_dir`` using ``loader``."""

    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: List[Path] = []
    for slug in slugs:
        try:
            html = loader(slug)
        except Exception as exc:  # pragma: no cover - network errors
            if progress:
                progress(slug, False, str(exc))
            continue

        path = output_dir / f"{slug}.html"
        path.write_text(html, encoding="utf-8")
        downloaded.append(path)
        if progress:
            progress(slug, True, None)
    return downloaded


def bulk_ingest_from_hellhades(
    db: ChampionDatabase,
    hellhades_html: str,
    loader: Callable[[str], str],
    *,
    limit: Optional[int] = None,
    progress: Optional[Callable[[Tuple[str, str], bool, Optional[str]], None]] = None,
) -> List[str]:
    """Ingest multiple champions discovered on the HellHades tier list."""

    champions = extract_champions(hellhades_html)
    if limit is not None:
        champions = champions[:limit]

    ingested: List[str] = []
    for slug, name in champions:
        try:
            html = loader(slug)
        except FileNotFoundError as exc:
            if progress:
                progress((slug, name), False, f"file not found: {exc}")
            continue
        except Exception as exc:  # pragma: no cover - network errors
            if progress:
                progress((slug, name), False, str(exc))
            continue
        try:
            ingest_source(db, html, slug=slug)
        except Exception as exc:  # pragma: no cover - parsing errors
            if progress:
                progress((slug, name), False, str(exc))
            continue
        ingested.append(slug)
        if progress:
            progress((slug, name), True, None)
    return ingested


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest champion pages into a SQLite database")
    parser.add_argument("--db", type=Path, default=Path("champions.db"), help="Database path")

    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("ingest", help="Ingest data from a file or URL")
    source_group = ingest_parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--file", type=Path, help="HTML file to ingest")
    source_group.add_argument("--url", help="Champion URL to download")
    ingest_parser.add_argument("--slug", help="Override slug for the champion")

    subparsers.add_parser("list", help="List stored champions")

    show_parser = subparsers.add_parser("show", help="Display champion data")
    show_parser.add_argument("identifier", help="Champion slug or name")

    delete_parser = subparsers.add_parser("delete", help="Remove a champion from the database")
    delete_parser.add_argument("identifier", help="Champion slug or name")

    bulk_parser = subparsers.add_parser(
        "bulk", help="Bulk ingest champions discovered on the HellHades tier list"
    )
    hellhades_group = bulk_parser.add_mutually_exclusive_group(required=True)
    hellhades_group.add_argument(
        "--hellhades-file",
        type=Path,
        help="Local HellHades tier list HTML file",
    )
    hellhades_group.add_argument(
        "--hellhades-url",
        help="HellHades tier list URL (default: https://hellhades.com/raid/tier-list/)",
        default="https://hellhades.com/raid/tier-list/",
    )
    bulk_parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of champions to ingest",
    )
    bulk_parser.add_argument(
        "--inteleria-template",
        default="https://www.inteleria.com/champion-list/{slug}/",
        help="Template URL used to download champion pages from Inteleria",
    )
    bulk_parser.add_argument(
        "--inteleria-dir",
        type=Path,
        help="Directory containing pre-downloaded Inteleria HTML files named <slug>.html",
    )
    bulk_parser.add_argument(
        "--save-html-dir",
        type=Path,
        help="Optional directory to save downloaded Inteleria pages during ingestion",
    )

    download_parser = subparsers.add_parser(
        "download", help="Download champion HTML pages for offline ingestion",
    )
    download_parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where downloaded HTML files will be stored",
    )
    download_parser.add_argument(
        "--slug",
        action="append",
        help="Champion slug to download (can be specified multiple times)",
    )
    download_parser.add_argument(
        "--hellhades-file",
        type=Path,
        help="Local HellHades tier list HTML file used to discover champions",
    )
    download_parser.add_argument(
        "--hellhades-url",
        default="https://hellhades.com/raid/tier-list/",
        help="HellHades tier list URL used to discover champions",
    )
    download_parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of champions to download when using the HellHades list",
    )
    download_parser.add_argument(
        "--inteleria-template",
        default="https://www.inteleria.com/champion-list/{slug}/",
        help="Template URL used to download champion pages from Inteleria",
    )

    return parser


def run_cli(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    database = ChampionDatabase(args.db)

    if args.command == "ingest":
        if args.file:
            html = args.file.read_text(encoding="utf-8")
            slug = args.slug
        else:
            html = fetch_url(args.url)
            slug = args.slug or slugify(args.url.rsplit("/", 1)[-1])
        ingest_source(database, html, slug=slug)
        return 0

    if args.command == "list":
        for record in database.list_champions():
            print(f"{record.slug}\t{record.name}")
        return 0

    if args.command == "show":
        data = database.load_champion(args.identifier)
        print(f"{data.name} [{data.slug}]")
        print("Basic info:")
        for key, value in sorted(data.basic_info.items()):
            print(f"  {key}: {value}")
        print("Stats:")
        for record in data.stats:
            variant = f" ({record.variant})" if record.variant else ""
            numeric = f" = {record.numeric_value}" if record.numeric_value is not None else ""
            print(f"  {record.label}{variant}: {record.raw_value}{numeric}")
        return 0

    if args.command == "delete":
        if database.delete_champion(args.identifier):
            print("Champion removed")
            return 0
        print("Champion not found", file=sys.stderr)
        return 1

    if args.command == "bulk":
        if args.hellhades_file:
            hellhades_html = args.hellhades_file.read_text(encoding="utf-8")
        else:
            hellhades_html = fetch_url(args.hellhades_url)

        def loader(slug: str) -> str:
            if args.inteleria_dir:
                path = args.inteleria_dir / f"{slug}.html"
                return path.read_text(encoding="utf-8")
            url = args.inteleria_template.format(slug=slug)
            return fetch_url(url)

        def progress_callback(champion: Tuple[str, str], success: bool, error: Optional[str]) -> None:
            slug, name = champion
            if success:
                print(f"Ingested {name} [{slug}]")
            else:
                if error:
                    print(f"Skipped {name} [{slug}]: {error}", file=sys.stderr)
                else:
                    print(f"Skipped {name} [{slug}]: unknown error", file=sys.stderr)

        ingested = bulk_ingest_from_hellhades(
            database,
            hellhades_html,
            loader,
            limit=args.limit,
            progress=progress_callback,
        )
        if args.save_html_dir and not args.inteleria_dir:
            args.save_html_dir.mkdir(parents=True, exist_ok=True)
            for slug in ingested:
                url = args.inteleria_template.format(slug=slug)
                html = fetch_url(url)
                (args.save_html_dir / f"{slug}.html").write_text(html, encoding="utf-8")
        print(f"Imported {len(ingested)} champions")
        return 0

    if args.command == "download":
        slugs: List[str] = []
        if args.slug:
            slugs.extend(args.slug)

        hellhades_html: Optional[str] = None
        if args.hellhades_file or args.hellhades_url:
            if args.hellhades_file:
                hellhades_html = args.hellhades_file.read_text(encoding="utf-8")
            elif not args.slug:
                hellhades_html = fetch_url(args.hellhades_url)

        if hellhades_html is not None:
            champions = extract_champions(hellhades_html)
            if args.limit is not None:
                champions = champions[: args.limit]
            slugs.extend([slug for slug, _ in champions])

        if not slugs:
            parser.error("No champions specified for download")

        seen = set()
        unique_slugs: List[str] = []
        for slug in slugs:
            if slug not in seen:
                seen.add(slug)
                unique_slugs.append(slug)
        slugs = unique_slugs

        def loader(slug: str) -> str:
            url = args.inteleria_template.format(slug=slug)
            return fetch_url(url)

        def progress(slug: str, success: bool, error: Optional[str]) -> None:
            if success:
                print(f"Downloaded {slug}")
            else:
                if error:
                    print(f"Skipped {slug}: {error}", file=sys.stderr)
                else:
                    print(f"Skipped {slug}: unknown error", file=sys.stderr)

        download_pages(slugs, loader, args.output_dir, progress=progress)
        return 0

    parser.error("Unknown command")
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_cli())
