from pathlib import Path

from inteleria.hellhades import extract_champions


def test_extract_champions_parses_unique_slugs():
    html = Path("tests/data/hellhades_tier_list.html").read_text(encoding="utf-8")

    champions = extract_champions(html)

    assert champions == [
        ("abbess", "Abbess"),
        ("galek", "Galek"),
        ("kael", "Kael"),
    ]
