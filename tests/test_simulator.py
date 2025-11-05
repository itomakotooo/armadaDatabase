from pathlib import Path

from inteleria.database import ChampionDatabase
from inteleria.parser import parse_champion
from inteleria.simulator import BattleSimulator


def load_sample(database: ChampionDatabase, name: str) -> None:
    html = Path(f"tests/data/{name}.html").read_text(encoding="utf-8")
    data = parse_champion(html)
    database.upsert_champion(data)


def test_simulator_returns_winner(tmp_path):
    db_path = tmp_path / "champions.db"
    database = ChampionDatabase(db_path)
    load_sample(database, "abbess")
    load_sample(database, "galek")

    simulator = BattleSimulator(database)
    result = simulator.simulate("abbess", "galek", seed=42, max_rounds=10)

    assert result.winner in {"Abbess", "Galek"}
    assert result.rounds <= 10
    assert len(result.log) == result.rounds or len(result.log) == 10
    assert all(entry.damage >= 1 for entry in result.log)
