from pathlib import Path

from inteleria.parser import parse_champion


def test_parse_champion_extracts_basic_info_and_stats():
    html = Path("tests/data/abbess.html").read_text(encoding="utf-8")
    data = parse_champion(html, slug="abbess")

    assert data.slug == "abbess"
    assert data.name == "Abbess"
    assert data.basic_info["Rarity"] == "Legendary"
    assert data.basic_info["Faction"] == "The Sacred Order"

    stats_by_key = data.stats_by_key()
    hp_variants = stats_by_key["hp"]
    assert len(hp_variants) == 2
    level_60 = next(record for record in hp_variants if record.variant == "level 60")
    assert level_60.raw_value == "15855"
    assert level_60.numeric_value == 15855

    crit_rate = stats_by_key["crit rate"][0]
    assert crit_rate.numeric_value == 0.15
