"""SQLite storage helpers for champion data."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, List, Optional

from .models import ChampionData, StatRecord


@dataclass
class ChampionRecord:
    id: int
    slug: str
    name: str


@dataclass
class StoredStat:
    key: str
    variant: Optional[str]
    label: str
    raw_value: str
    numeric_value: Optional[float]


class ChampionDatabase:
    """Simple wrapper around SQLite for champion data storage."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.executescript(
                """
                CREATE TABLE IF NOT EXISTS champions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS basic_info (
                    champion_id INTEGER NOT NULL,
                    info_key TEXT NOT NULL,
                    info_value TEXT NOT NULL,
                    PRIMARY KEY (champion_id, info_key),
                    FOREIGN KEY (champion_id) REFERENCES champions(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS stats (
                    champion_id INTEGER NOT NULL,
                    stat_key TEXT NOT NULL,
                    stat_variant TEXT NOT NULL DEFAULT "",
                    stat_label TEXT NOT NULL,
                    raw_value TEXT NOT NULL,
                    numeric_value REAL,
                    PRIMARY KEY (champion_id, stat_key, stat_variant),
                    FOREIGN KEY (champion_id) REFERENCES champions(id) ON DELETE CASCADE
                );
                """
            )
            connection.commit()

    def upsert_champion(self, data: ChampionData) -> ChampionRecord:
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT id FROM champions WHERE slug = ?", (data.slug,))
            row = cursor.fetchone()
            if row is None:
                cursor.execute(
                    "INSERT INTO champions (slug, name) VALUES (?, ?)",
                    (data.slug, data.name),
                )
                champion_id = cursor.lastrowid
            else:
                (champion_id,) = row
                cursor.execute(
                    "UPDATE champions SET name = ? WHERE id = ?",
                    (data.name, champion_id),
                )
            cursor.execute("DELETE FROM basic_info WHERE champion_id = ?", (champion_id,))
            cursor.execute("DELETE FROM stats WHERE champion_id = ?", (champion_id,))
            cursor.executemany(
                "INSERT INTO basic_info (champion_id, info_key, info_value) VALUES (?, ?, ?)",
                [
                    (champion_id, key, value)
                    for key, value in sorted(data.basic_info.items())
                ],
            )
            cursor.executemany(
                "INSERT INTO stats (champion_id, stat_key, stat_variant, stat_label, raw_value, numeric_value)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        champion_id,
                        record.key,
                        record.variant or "",
                        record.label,
                        record.raw_value,
                        record.numeric_value,
                    )
                    for record in data.stats
                ],
            )
            connection.commit()
            return ChampionRecord(id=champion_id, slug=data.slug, name=data.name)

    def list_champions(self) -> List[ChampionRecord]:
        with self.connect() as connection:
            cursor = connection.execute(
                "SELECT id, slug, name FROM champions ORDER BY name COLLATE NOCASE"
            )
            return [ChampionRecord(*row) for row in cursor.fetchall()]

    def get_champion(self, identifier: str) -> Optional[ChampionRecord]:
        token = identifier.strip().lower()
        with self.connect() as connection:
            cursor = connection.execute(
                "SELECT id, slug, name FROM champions WHERE slug = ?",
                (token,),
            )
            row = cursor.fetchone()
            if row:
                return ChampionRecord(*row)
            cursor = connection.execute(
                "SELECT id, slug, name FROM champions WHERE LOWER(name) = ?",
                (token,),
            )
            row = cursor.fetchone()
            if row:
                return ChampionRecord(*row)
        return None

    def load_champion(self, identifier: str) -> ChampionData:
        record = self.get_champion(identifier)
        if record is None:
            raise KeyError(f"Champion '{identifier}' not found")
        with self.connect() as connection:
            cursor = connection.execute(
                "SELECT info_key, info_value FROM basic_info WHERE champion_id = ?",
                (record.id,),
            )
            basic_info = {key: value for key, value in cursor.fetchall()}
            cursor = connection.execute(
                "SELECT stat_key, stat_variant, stat_label, raw_value, numeric_value"
                " FROM stats WHERE champion_id = ?",
                (record.id,),
            )
            stats = [
                StatRecord(
                    key=stat_key,
                    variant=variant or None,
                    label=label,
                    raw_value=raw_value,
                    numeric_value=numeric_value,
                )
                for stat_key, variant, label, raw_value, numeric_value in cursor.fetchall()
            ]
        return ChampionData(slug=record.slug, name=record.name, basic_info=basic_info, stats=stats)

    def stats_for(self, identifier: str) -> List[StoredStat]:
        record = self.get_champion(identifier)
        if record is None:
            raise KeyError(f"Champion '{identifier}' not found")
        with self.connect() as connection:
            cursor = connection.execute(
                "SELECT stat_key, stat_variant, stat_label, raw_value, numeric_value"
                " FROM stats WHERE champion_id = ?",
                (record.id,),
            )
            return [
                StoredStat(
                    key=stat_key,
                    variant=variant or None,
                    label=label,
                    raw_value=raw_value,
                    numeric_value=numeric_value,
                )
                for stat_key, variant, label, raw_value, numeric_value in cursor.fetchall()
            ]

    def delete_champion(self, identifier: str) -> bool:
        record = self.get_champion(identifier)
        if record is None:
            return False
        with self.connect() as connection:
            connection.execute("DELETE FROM champions WHERE id = ?", (record.id,))
            connection.commit()
        return True


__all__ = ["ChampionDatabase", "ChampionRecord", "StoredStat"]
