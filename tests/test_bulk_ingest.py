from pathlib import Path

from inteleria.database import ChampionDatabase
from inteleria.scraper import bulk_ingest_from_hellhades


def test_bulk_ingest_from_hellhades_uses_loader_and_skips_missing(tmp_path):
    db_path = tmp_path / "champions.db"
    database = ChampionDatabase(db_path)
    hellhades_html = Path("tests/data/hellhades_tier_list.html").read_text(encoding="utf-8")

    loaded_slugs = []

    def loader(slug: str) -> str:
        loaded_slugs.append(slug)
        path = Path("tests/data") / f"{slug}.html"
        return path.read_text(encoding="utf-8")

    ingested = bulk_ingest_from_hellhades(database, hellhades_html, loader)

    assert loaded_slugs == ["abbess", "galek", "kael"]
    assert ingested == ["abbess", "galek"]

    stored = {record.slug for record in database.list_champions()}
    assert stored == {"abbess", "galek"}
