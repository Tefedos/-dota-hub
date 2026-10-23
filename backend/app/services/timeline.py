"""Evidence-first chronology of parsed OpenDota events."""

from collections.abc import Mapping
from hashlib import sha256
from math import isfinite
from typing import Any

from app.models.matches import NormalizedMatch, QualityStatus, Team
from app.models.timeline import AdvantagePoint, TimelineActor, TimelineEvent, TimelineReport, TurningPoint

FAMILIES = ("objectives", "kills_log", "buyback_log", "purchase_log", "teamfights", "radiant_gold_adv", "radiant_xp_adv")
EVENT_TYPES = ("first_blood", "hero_kill", "tower", "building", "roshan", "aegis", "buyback", "purchase", "teamfight")
FAMILY_TYPES = {"objectives": EVENT_TYPES[:1] + EVENT_TYPES[2:6], "kills_log": ("hero_kill",),
                "buyback_log": ("buyback",), "purchase_log": ("purchase",), "teamfights": ("teamfight",)}


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _time(value: object, duration: int | None) -> int | None:
    result = _int(value)
    return result if result is not None and -3600 <= result <= (duration + 60 if duration else 86400) else None


def _clock(seconds: int) -> str:
    minutes, remainder = divmod(abs(seconds), 60)
    return ("-" if seconds < 0 else "") + f"{minutes}:{remainder:02d}"


def _actor(match: NormalizedMatch, slot: object) -> TimelineActor | None:
    number = _int(slot)
    if number is None:
        return None
    for player in match.summary.hero_roster:
        if player.player_slot == number:
            return TimelineActor(player_slot=number, team=player.team, hero_id=player.hero_id, hero_name=player.hero_name)
    return None


def _side(value: object) -> Team | None:
    if value == "radiant" or _int(value) == 0:
        return Team.RADIANT
    if value == "dire" or _int(value) == 1:
        return Team.DIRE
    return None


def _objective(item: Mapping[str, Any]) -> tuple[str, Team | None, str] | None:
    kind, key = item.get("type"), item.get("key")
    if kind == "CHAT_MESSAGE_FIRSTBLOOD":
        return "first_blood", None, "Первая кровь"
    if kind == "CHAT_MESSAGE_ROSHAN_KILL":
        return "roshan", _side(item.get("team")), "Убийство Рошана"
    if kind in ("CHAT_MESSAGE_AEGIS", "CHAT_MESSAGE_AEGIS_TAKE"):
        return "aegis", _side(item.get("team")), "Подобран Aegis"
    if kind == "building_kill" and isinstance(key, str):
        owner = Team.RADIANT if key.startswith("npc_dota_goodguys_") else Team.DIRE if key.startswith("npc_dota_badguys_") else None
        attacker = Team.DIRE if owner == Team.RADIANT else Team.RADIANT if owner == Team.DIRE else None
        if "_tower" in key:
            return "tower", attacker, "Разрушена башня"
        if owner is not None:
            return "building", attacker, "Разрушено строение"
    return None


def _event(*, key: str, start: int, kind: str, team: Team | None, actors: tuple[TimelineActor, ...],
           description: str, ref: str, evidence: dict[str, Any], end: int | None = None) -> TimelineEvent:
    finish = start if end is None else end
    return TimelineEvent(
        id=sha256(key.encode()).hexdigest()[:16], time_seconds=start if end is None else None,
        time_start=start, time_end=finish, time_precision="interval" if end is not None else "exact",
        display_clock=f"{_clock(start)}–{_clock(finish)}" if end is not None else _clock(start),
        type=kind, team=team, side=team, actors=actors, description=description, evidence=evidence,
        evidence_quality="confirmed" if team is not None or kind in ("first_blood", "teamfight") else "partial",
        source_field=ref.split(".")[-1].split("[")[0], original_ref=ref,
        original_refs=(ref,), dedupe_key=key,
        reason_codes=("SOURCE_" + kind.upper(),),
    )


def _curve(values: tuple[int | float | None, ...] | None, name: str) -> tuple[tuple[AdvantagePoint, ...], bool]:
    if values is None:
        return (), False
    points = []
    valid = bool(values)
    for minute, value in enumerate(values):
        if value is None or isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
            valid = False
            continue
        points.append(AdvantagePoint(time_seconds=minute * 60, value=value,
                                     advantage_for=Team.RADIANT if value > 0 else Team.DIRE if value < 0 else None,
                                     source_field=name))
    return tuple(points), valid


def _turning(gold: tuple[AdvantagePoint, ...], xp: tuple[AdvantagePoint, ...],
             events: tuple[TimelineEvent, ...]) -> tuple[TurningPoint, ...]:
    series = ({p.time_seconds: p.value for p in gold}, {p.time_seconds: p.value for p in xp})
    candidates: list[tuple[int, float, float | None, float | None]] = []
    for start in sorted(set(series[0]) | set(series[1])):
        deltas: list[float | None] = []
        for curve in series:
            deltas.append(float(curve[start + 180] - curve[start]) if all(start + 60 * i in curve for i in range(4)) else None)
        gd, xd = deltas
        strength = max(abs(gd or 0) / 3000, abs(xd or 0) / 4000)
        if strength >= 1:
            primary = gd if abs(gd or 0) / 3000 >= abs(xd or 0) / 4000 else xd
            assert primary is not None
            candidates.append((start, primary, gd, xd))
    chosen: list[tuple[int, float, float | None, float | None]] = []
    for candidate in sorted(candidates, key=lambda c: (-max(abs(c[2] or 0) / 3000, abs(c[3] or 0) / 4000), c[0])):
        if all(candidate[0] + 180 <= old[0] or old[0] + 180 <= candidate[0] for old in chosen):
            chosen.append(candidate)
    result = []
    for start, delta, gd, xd in sorted(chosen):
        related = tuple(e.id for e in events if e.type != "purchase" and e.time_start <= start + 240 and e.time_end >= start - 60)
        result.append(TurningPoint(
            time_start=start, time_end=start + 180, delta=delta, gold_delta=gd, xp_delta=xd,
            direction=Team.RADIANT if delta > 0 else Team.DIRE,
            reason_codes=("SIGNIFICANT_ADVANTAGE_CHANGE", "NEARBY_CONFIRMED_EVENTS" if related else "NO_NEARBY_EVENTS"),
            confidence="medium" if gd is not None and xd is not None and gd * xd > 0 and related else "low",
            related_event_ids=related,
            evidence={"window_minutes": 3, "gold_threshold": 3000, "xp_threshold": 4000,
                      "gold_delta": gd, "xp_delta": xd},
        ))
    return tuple(result)


def analyze_timeline(match: NormalizedMatch) -> TimelineReport:
    raw = match.raw.events
    duration = match.summary.duration
    by_key: dict[str, TimelineEvent] = {}
    malformed: set[str] = set()

    def add(event: TimelineEvent) -> None:
        old = by_key.get(event.dedupe_key)
        by_key[event.dedupe_key] = event if old is None else old.model_copy(update={
            "original_refs": tuple(sorted(set(old.original_refs + event.original_refs)))})

    for index, item in enumerate(raw.objectives or ()):
        if not isinstance(item, dict):
            malformed.add("objectives")
            continue
        classification = _objective(item)
        if classification is None:
            continue
        seconds = _time(item.get("time"), duration)
        if seconds is None:
            malformed.add("objectives")
            continue
        kind, side, description = classification
        slot = item.get("player_slot", item.get("slot"))
        actor = _actor(match, slot)
        if slot is not None and actor is None:
            malformed.add("objectives")
        if side is None and actor is not None and kind in ("first_blood", "roshan", "aegis"):
            side = actor.team
        key = f"{kind}:{seconds}:{item.get('key')}:{actor.player_slot if actor else 'unknown'}"
        add(_event(key=key, start=seconds, kind=kind, team=side, actors=(actor,) if actor else (),
                   description=description, ref=f"objectives[{index}]",
                   evidence={name: item[name] for name in ("type", "key", "player_slot", "victim_player_slot") if name in item}))

    for family, kind, label in (("kills_log", "hero_kill", "Убийство героя"),
                                ("buyback_log", "buyback", "Выкуп"),
                                ("purchase_log", "purchase", "Покупка предмета")):
        records: list[tuple[str, object, int | None]] = []
        top = getattr(raw, family)
        records.extend((f"{family}[{i}]", item, None) for i, item in enumerate(top or ()))
        for logs in raw.player_logs:
            entries = getattr(logs, family)
            records.extend((f"players[{logs.player_slot}].{family}[{i}]", item, logs.player_slot)
                           for i, item in enumerate(entries or ()))
        for ref, record, parent_slot in records:
            if not isinstance(record, dict):
                malformed.add(family)
                continue
            seconds = _time(record.get("time"), duration)
            claimed = record.get("player_slot", record.get("slot"))
            if seconds is None or (claimed is not None and parent_slot is not None and claimed != parent_slot):
                malformed.add(family)
                continue
            actor = _actor(match, claimed if claimed is not None else parent_slot)
            if (claimed is not None or parent_slot is not None) and actor is None:
                malformed.add(family)
                continue
            value = record.get("key")
            if kind == "hero_kill" and (not isinstance(value, str) or not value.startswith("npc_dota_hero_")):
                malformed.add(family)
                continue
            if kind == "purchase" and (not isinstance(value, str) or not value.strip()):
                malformed.add(family)
                continue
            key = f"{kind}:{seconds}:{actor.player_slot if actor else 'unknown'}:{value if kind != 'buyback' else ''}"
            if kind == "purchase":
                key += f":{ref}"
            add(_event(key=key, start=seconds, kind=kind, team=actor.team if actor else None,
                       actors=(actor,) if actor else (), description=label, ref=ref,
                       evidence={name: record[name] for name in ("key", "type") if name in record}))

    for index, item in enumerate(raw.teamfights or ()):
        if not isinstance(item, dict):
            malformed.add("teamfights")
            continue
        start, end = _time(item.get("start"), duration), _time(item.get("end"), duration)
        if start is None or end is None or end < start:
            malformed.add("teamfights")
            continue
        evidence: dict[str, Any] = {"source_start": start, "source_end": end}
        deaths = _int(item.get("deaths"))
        if deaths is not None and deaths >= 0:
            evidence["deaths"] = deaths
        players = item.get("players")
        if isinstance(players, list) and players and all(isinstance(p, dict) for p in players):
            counts = [p.get("buybacks") for p in players if isinstance(p, dict)]
            numbers = [_int(value) for value in counts]
            if all(number is not None and number >= 0 for number in numbers):
                evidence["buybacks"] = sum(number for number in numbers if number is not None)
        add(_event(key=f"teamfight:{start}:{end}", start=start, end=end, kind="teamfight", team=None,
                   actors=(), description="Командная драка (интервал OpenDota)",
                   ref=f"teamfights[{index}]", evidence=evidence))

    events = tuple(sorted(by_key.values(), key=lambda e: (e.time_start, e.time_end, e.type, e.id)))
    events = tuple(e.model_copy(update={"related_event_ids": tuple(other.id for other in events
        if other.type == "hero_kill" and e.time_start <= other.time_start <= e.time_end)})
        if e.type == "teamfight" else e for e in events)
    gold, gold_valid = _curve(raw.radiant_gold_adv, "radiant_gold_adv")
    xp, xp_valid = _curve(raw.radiant_xp_adv, "radiant_xp_adv")
    if raw.radiant_gold_adv is not None and not gold_valid:
        malformed.add("radiant_gold_adv")
    if raw.radiant_xp_adv is not None and not xp_valid:
        malformed.add("radiant_xp_adv")
    available = {family: (getattr(raw, family) is not None or any(getattr(p, family) is not None for p in raw.player_logs))
                 if family in ("kills_log", "buyback_log", "purchase_log") else getattr(raw, family) is not None
                 for family in FAMILIES}
    supported = tuple(t for t in EVENT_TYPES if any(available[f] and t in kinds for f, kinds in FAMILY_TYPES.items()))
    missing = tuple(t for t in EVENT_TYPES if t not in supported)
    content = bool(events or gold or xp)
    quality = (QualityStatus.UNAVAILABLE if not content else QualityStatus.COMPLETE
               if all(available.values()) and not malformed and match.source_status != "FOUND_PARTIAL"
               else QualityStatus.PARTIAL)
    limitations = []
    if not all(available.values()):
        limitations.append("Недоступны источники: " + ", ".join(f for f in FAMILIES if not available[f]))
    if malformed:
        limitations.append("Пропущены некорректные записи: " + ", ".join(sorted(malformed)))
    if match.source_status == "FOUND_PARTIAL":
        limitations.append("Исходный матч OpenDota разобран частично")
    if not gold:
        limitations.append("График преимущества по золоту недоступен")
    if not xp:
        limitations.append("График преимущества по опыту недоступен")
    return TimelineReport(
        match_id=match.summary.match_id, quality=quality, timeline_data_status=quality,
        available_types=tuple(t for t in EVENT_TYPES if any(e.type == t for e in events)),
        supported_event_types=supported, missing_event_types=missing,
        event_coverage=round(sum(available.values()) / len(FAMILIES), 4),
        empty_state_text="Данные хронологии недоступны" if not content else "Подтверждённые события не найдены" if not events else None,
        events=events, gold_adv_points=gold, xp_adv_points=xp,
        turning_points=_turning(gold, xp, events), limitations=tuple(limitations),
    )


def filter_timeline_events(report: TimelineReport, *, event_type: str | None = None,
                           team: Team | None = None) -> tuple[TimelineEvent, ...]:
    return tuple(e for e in report.events if (event_type is None or e.type == event_type)
                 and (team is None or e.team == team))
