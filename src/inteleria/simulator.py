"""Battle simulation utilities for champions stored in the database."""
from __future__ import annotations

import argparse
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .database import ChampionDatabase
from .models import StatRecord


STAT_ALIASES = {
    "hp": {"hp", "health"},
    "attack": {"attack", "atk"},
    "defense": {"defense", "def"},
    "speed": {"speed", "spd"},
    "crit rate": {"crit rate", "critical rate", "c rate"},
    "crit damage": {"crit damage", "critical damage", "c dmg"},
    "resistance": {"resistance", "res"},
    "accuracy": {"accuracy", "acc"},
}


def matches_key(key: str, target: str) -> bool:
    canonical = " ".join(part for part in key.lower().split() if part)
    synonyms = STAT_ALIASES.get(target, {target})
    return any(token in canonical for token in synonyms)


@dataclass
class Combatant:
    name: str
    slug: str
    max_hp: float
    attack: float
    defense: float
    speed: float
    crit_rate: float
    crit_damage: float
    resistance: float
    accuracy: float

    def copy(self) -> "Combatant":
        return Combatant(
            name=self.name,
            slug=self.slug,
            max_hp=self.max_hp,
            attack=self.attack,
            defense=self.defense,
            speed=self.speed,
            crit_rate=self.crit_rate,
            crit_damage=self.crit_damage,
            resistance=self.resistance,
            accuracy=self.accuracy,
        )


@dataclass
class CombatLogEntry:
    round_number: int
    attacker: str
    defender: str
    damage: int
    remaining_hp: int
    was_crit: bool


@dataclass
class SimulationResult:
    winner: Optional[str]
    rounds: int
    log: List[CombatLogEntry]


class BattleSimulator:
    """Runs deterministic battle simulations based on champion stats."""

    def __init__(self, database: ChampionDatabase, rng: Optional[random.Random] = None) -> None:
        self.database = database
        self.rng = rng or random.Random()

    def _resolve_combatant(self, identifier: str) -> Combatant:
        data = self.database.load_champion(identifier)
        stats = data.stats
        stat_lookup: Dict[str, List[StatRecord]] = {}
        for record in stats:
            stat_lookup.setdefault(record.key, []).append(record)

        def pick_value(target: str, default: float) -> float:
            entries = [
                candidate
                for key, values in stat_lookup.items()
                if matches_key(key, target)
                for candidate in values
            ]
            if not entries:
                return default
            # Prefer highest numeric value available.
            numeric_entries = [entry for entry in entries if entry.numeric_value is not None]
            if numeric_entries:
                selected = max(numeric_entries, key=lambda item: item.numeric_value)  # type: ignore[arg-type]
                return float(selected.numeric_value)  # type: ignore[arg-type]
            # Fallback to parsing raw values into float if possible.
            for entry in entries:
                try:
                    return float(entry.raw_value.replace(",", "").rstrip("%"))
                except ValueError:
                    continue
            return default

        crit_rate = pick_value("crit rate", 0.15)
        if crit_rate > 1:
            crit_rate = crit_rate / 100.0
        crit_damage = pick_value("crit damage", 0.5)
        if crit_damage > 2:  # most tables store crit damage as percentages like 63
            crit_damage = crit_damage / 100.0

        return Combatant(
            name=data.name,
            slug=data.slug,
            max_hp=pick_value("hp", 1000.0),
            attack=pick_value("attack", 100.0),
            defense=pick_value("defense", 100.0),
            speed=pick_value("speed", 100.0),
            crit_rate=crit_rate,
            crit_damage=crit_damage,
            resistance=pick_value("resistance", 0.0),
            accuracy=pick_value("accuracy", 0.0),
        )

    def _perform_attack(self, attacker: Combatant, defender_defense: float) -> Tuple[int, bool]:
        crit_roll = self.rng.random()
        was_crit = crit_roll < attacker.crit_rate
        crit_multiplier = 1.0 + (attacker.crit_damage if was_crit else 0.0)
        base_damage = attacker.attack * crit_multiplier
        mitigation = 100.0 / (100.0 + defender_defense)
        damage = max(1.0, base_damage * mitigation)
        return int(round(damage)), was_crit

    def simulate(self, first: str, second: str, *, max_rounds: int = 50, seed: Optional[int] = None) -> SimulationResult:
        if seed is not None:
            self.rng.seed(seed)

        a = self._resolve_combatant(first)
        b = self._resolve_combatant(second)
        combatants = sorted([a.copy(), b.copy()], key=lambda c: c.speed, reverse=True)
        hp = {combatants[0].slug: combatants[0].max_hp, combatants[1].slug: combatants[1].max_hp}
        log: List[CombatLogEntry] = []

        for round_number in range(1, max_rounds + 1):
            attacker = combatants[(round_number - 1) % 2]
            defender = combatants[round_number % 2]
            damage, was_crit = self._perform_attack(attacker, defender.defense)
            hp[defender.slug] -= damage
            log.append(
                CombatLogEntry(
                    round_number=round_number,
                    attacker=attacker.name,
                    defender=defender.name,
                    damage=damage,
                    remaining_hp=max(0, int(math.ceil(hp[defender.slug]))),
                    was_crit=was_crit,
                )
            )
            if hp[defender.slug] <= 0:
                return SimulationResult(winner=attacker.name, rounds=round_number, log=log)

        # Determine winner by remaining HP if no knockout occurred.
        remaining = sorted(hp.items(), key=lambda item: item[1], reverse=True)
        if math.isclose(remaining[0][1], remaining[1][1], rel_tol=1e-3):
            winner = None
        else:
            winner_slug, _ = remaining[0]
            winner = next(c.name for c in combatants if c.slug == winner_slug)
        return SimulationResult(winner=winner, rounds=max_rounds, log=log)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Simulate battles between stored champions")
    parser.add_argument("--db", type=Path, default=Path("champions.db"), help="Database path")
    parser.add_argument("first", help="Slug or name of the first champion")
    parser.add_argument("second", help="Slug or name of the second champion")
    parser.add_argument("--seed", type=int, help="Random seed for the simulation")
    parser.add_argument("--max-rounds", type=int, default=50, help="Maximum number of rounds")
    parser.add_argument("--show-log", action="store_true", help="Print the combat log")
    return parser


def run_cli(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    simulator = BattleSimulator(ChampionDatabase(args.db))
    result = simulator.simulate(
        args.first,
        args.second,
        max_rounds=args.max_rounds,
        seed=args.seed,
    )
    if args.show_log:
        for entry in result.log:
            crit_marker = "!" if entry.was_crit else ""
            print(
                f"Round {entry.round_number}: {entry.attacker} hits {entry.defender} for {entry.damage}{crit_marker}."
                f" {entry.defender} HP: {entry.remaining_hp}"
            )
    if result.winner:
        print(f"Winner: {result.winner} in {result.rounds} rounds")
    else:
        print("Result: draw")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_cli())
