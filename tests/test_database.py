from pathlib import Path

from inteleria.database import ChampionDatabase
from inteleria.parser import parse_champion


def test_database_round_trip(tmp_path):
    db_path = tmp_path / "champions.db"
    database = ChampionDatabase(db_path)
    html = Path("tests/data/galek.html").read_text(encoding="utf-8")
    data = parse_champion(html)

    database.upsert_champion(data)

    stored = database.load_champion("galek")
    assert stored.name == "Galek"
    assert stored.basic_info["Faction"] == "Orcs"

    stats = {record.label: record.numeric_value for record in stored.stats}
    assert stats["HP (Level 60)"] == 13875
