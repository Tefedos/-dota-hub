from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime
from math import isfinite
from typing import Any, TypeGuard, cast

from pydantic import JsonValue

from app.models.matches import (
    DataQuality,
    DerivedMetric,
    DraftAction,
    DraftRawData,
    EvidenceStatus,
    FarmPositionEvidence,
    HeroRosterEntry,
    MatchEventRawData,
    MatchSummary,
    MetricStatus,
    NormalizedMatch,
    NormalizedRawData,
    PlayerDerivedStats,
    PlayerEventLogs,
    PlayerField,
    PlayerStat,
    Position,
    PositionEvidence,
    QualityStatus,
    SummaryField,
    Team,
    TeamSummary,
)

MAX_BIGINT = 2**63 - 1
CORE_PLAYER_FIELDS = (
    PlayerField.HERO_ID, PlayerField.KILLS, PlayerField.DEATHS, PlayerField.ASSISTS,
    PlayerField.LAST_HITS, PlayerField.DENIES, PlayerField.GPM, PlayerField.XPM,
    PlayerField.HERO_DAMAGE, PlayerField.TOWER_DAMAGE, PlayerField.HERO_HEALING,
    PlayerField.NET_WORTH,
)
LANE_ROLES = {
    1: Position.SAFE_LANE,
    2: Position.MID_LANE,
    3: Position.OFF_LANE,
    4: Position.JUNGLE,
}


class MatchNormalizationError(ValueError):
    pass


def _is_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)


def _int(value: object, *, minimum: int = 0, maximum: int = MAX_BIGINT) -> int | None:
    return value if _is_int(value) and minimum <= value <= maximum else None


def _float(value: object, *, maximum: float = 1_000_000_000) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= maximum and isfinite(value):
        return float(value)
    return None


def _id(value: object, *, maximum: int = 2**64 - 1) -> str | None:
    if _is_int(value) and 0 < value <= maximum:
        return str(value)
    if isinstance(value, str) and value.isascii() and value.isdecimal() and not value.startswith("0"):
        parsed = int(value)
        return value if 0 < parsed <= maximum else None
    return None


def _quality(complete: bool, any_available: bool) -> QualityStatus:
    if complete:
        return QualityStatus.COMPLETE
    return QualityStatus.PARTIAL if any_available else QualityStatus.UNAVAILABLE


def _position(player: Mapping[str, Any]) -> PositionEvidence:
    lane_role = _int(player.get("lane_role"), maximum=4)
    if lane_role in LANE_ROLES:
        return PositionEvidence(
            position=LANE_ROLES[lane_role], evidence=EvidenceStatus.CONFIRMED,
            confidence=1.0, source_field="lane_role",
        )
    return PositionEvidence(position=Position.UNKNOWN, evidence=EvidenceStatus.UNKNOWN)


def _item_timings(value: object) -> dict[str, tuple[int, ...]] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, tuple[int, ...]] = {}
    for key in sorted(value):
        if not isinstance(key, str) or not key:
            return None
        times = value[key]
        if _is_int(times):
            result[key] = (times,)
        elif isinstance(times, list) and all(_is_int(item) for item in times):
            result[key] = tuple(times)
        else:
            return None
    return result


def _player(
    source: Mapping[str, Any], *, team: Team, number: int, slot: int,
    hero_names: Mapping[int, str],
) -> PlayerStat:
    values: dict[PlayerField, object] = {
        PlayerField.HERO_ID: _int(source.get("hero_id"), minimum=1),
        PlayerField.ACCOUNT_ID: _id(source.get("account_id")),
        PlayerField.STEAM_ID: _id(source.get("steam_id", source.get("steamid"))),
        PlayerField.KILLS: _int(source.get("kills")),
        PlayerField.DEATHS: _int(source.get("deaths")),
        PlayerField.ASSISTS: _int(source.get("assists")),
        PlayerField.LAST_HITS: _int(source.get("last_hits")),
        PlayerField.DENIES: _int(source.get("denies")),
        PlayerField.GPM: _int(source.get("gold_per_min")),
        PlayerField.XPM: _int(source.get("xp_per_min")),
        PlayerField.HERO_DAMAGE: _int(source.get("hero_damage")),
        PlayerField.TOWER_DAMAGE: _int(source.get("tower_damage")),
        PlayerField.HERO_HEALING: _int(source.get("hero_healing")),
        PlayerField.NET_WORTH: _int(source.get("net_worth")),
        PlayerField.LEVEL: _int(source.get("level"), minimum=1, maximum=100),
        PlayerField.STUN_DURATION_SECONDS: _float(source.get("stuns")),
        PlayerField.BUYBACK_COUNT: _int(source.get("buyback_count")),
        PlayerField.OBS_PLACED: _int(source.get("obs_placed")),
        PlayerField.SEN_PLACED: _int(source.get("sen_placed")),
        PlayerField.OBSERVER_KILLS: _int(source.get("observer_kills")),
        PlayerField.SENTRY_KILLS: _int(source.get("sentry_kills")),
    }
    items = tuple(_int(source.get(f"item_{index}")) for index in range(6))
    backpack_items = tuple(_int(source.get(f"backpack_{index}")) for index in range(3))
    neutral = _int(source.get("item_neutral"))
    timings = _item_timings(source.get("purchase_time"))
    position = _position(source)
    estimated_position = _int(source.get("position_est"), minimum=1, maximum=5)
    performance_position = FarmPositionEvidence(
        position=estimated_position, evidence=EvidenceStatus.ESTIMATED, source_field="position_est",
    ) if estimated_position is not None else FarmPositionEvidence()
    available = [field for field in PlayerField if values.get(field) is not None]
    if all(item is not None for item in items):
        available.append(PlayerField.ITEMS)
    if all(item is not None for item in backpack_items):
        available.append(PlayerField.BACKPACK_ITEMS)
    if neutral is not None:
        available.append(PlayerField.NEUTRAL_ITEM)
    if timings is not None:
        available.append(PlayerField.ITEM_TIMINGS)
    if position.evidence == EvidenceStatus.CONFIRMED:
        available.append(PlayerField.POSITION)
    if estimated_position is not None:
        available.append(PlayerField.PERFORMANCE_POSITION)
    hero_id = cast(int | None, values[PlayerField.HERO_ID])
    nickname = source.get("personaname")
    display_name = " ".join(nickname.split())[:80] if isinstance(nickname, str) else ""
    is_anonymous = not bool(display_name)
    return PlayerStat(
        team=team, player_slot=slot, team_player_number=number,
        display_name=display_name or "Анонимный игрок",
        name_source=None if is_anonymous else "opendota", is_anonymous=is_anonymous,
        hero_id=hero_id, hero_name=hero_names.get(hero_id) if hero_id is not None else None,
        account_id=cast(str | None, values[PlayerField.ACCOUNT_ID]),
        steam_id=cast(str | None, values[PlayerField.STEAM_ID]),
        kills=cast(int | None, values[PlayerField.KILLS]),
        deaths=cast(int | None, values[PlayerField.DEATHS]),
        assists=cast(int | None, values[PlayerField.ASSISTS]),
        last_hits=cast(int | None, values[PlayerField.LAST_HITS]),
        denies=cast(int | None, values[PlayerField.DENIES]),
        gpm=cast(int | None, values[PlayerField.GPM]),
        xpm=cast(int | None, values[PlayerField.XPM]),
        hero_damage=cast(int | None, values[PlayerField.HERO_DAMAGE]),
        tower_damage=cast(int | None, values[PlayerField.TOWER_DAMAGE]),
        hero_healing=cast(int | None, values[PlayerField.HERO_HEALING]),
        net_worth=cast(int | None, values[PlayerField.NET_WORTH]),
        level=cast(int | None, values[PlayerField.LEVEL]),
        stun_duration_seconds=cast(float | None, values[PlayerField.STUN_DURATION_SECONDS]),
        buyback_count=cast(int | None, values[PlayerField.BUYBACK_COUNT]),
        obs_placed=cast(int | None, values[PlayerField.OBS_PLACED]),
        sen_placed=cast(int | None, values[PlayerField.SEN_PLACED]),
        observer_kills=cast(int | None, values[PlayerField.OBSERVER_KILLS]),
        sentry_kills=cast(int | None, values[PlayerField.SENTRY_KILLS]),
        performance_position=performance_position,
        items=items, backpack_items=backpack_items, neutral_item=neutral, item_timings=timings, position=position,
        available_fields=tuple(field for field in PlayerField if field in available),
    )


def _players(match: Mapping[str, Any], hero_names: Mapping[int, str]) -> tuple[PlayerStat, ...]:
    source = match.get("players")
    if source is None:
        return ()
    if not isinstance(source, list) or len(source) > 10:
        raise MatchNormalizationError("players must be a list with at most ten entries")
    by_slot: dict[int, Mapping[str, Any]] = {}
    for player in source:
        if not isinstance(player, dict):
            raise MatchNormalizationError("each player must be an object")
        slot = _int(player.get("player_slot"), maximum=255)
        if slot is None:
            raise MatchNormalizationError("player_slot must be an integer from 0 to 255")
        if slot in by_slot:
            raise MatchNormalizationError("player_slot values must be unique")
        by_slot[slot] = player
    radiant_slots = sorted(slot for slot in by_slot if slot < 128)
    dire_slots = sorted(slot for slot in by_slot if slot >= 128)
    if len(radiant_slots) > 5 or len(dire_slots) > 5:
        raise MatchNormalizationError("each team can contain at most five players")
    numbers = {
        **{slot: index + 1 for index, slot in enumerate(radiant_slots)},
        **{slot: index + 1 for index, slot in enumerate(dire_slots)},
    }
    return tuple(
        _player(
            by_slot[slot], team=Team.RADIANT if slot < 128 else Team.DIRE,
            number=numbers[slot], slot=slot, hero_names=hero_names,
        )
        for slot in sorted(by_slot)
    )


def _draft(value: object) -> DraftRawData:
    if value is None:
        return DraftRawData(
            available=False, actions=(), duplicate_orders=(), duplicate_actions_source_orders=(),
            missing_orders=(), invalid_source_orders=(), completeness=QualityStatus.UNAVAILABLE,
        )
    if not isinstance(value, list):
        raise MatchNormalizationError("picks_bans must be a list or null")
    actions: list[DraftAction] = []
    invalid: list[int] = []
    seen_actions: set[tuple[bool | None, int | None, int | None, int | None]] = set()
    duplicate_actions: list[int] = []
    for source_order, item in enumerate(value):
        if not isinstance(item, dict):
            item = {}
            invalid.append(source_order)
        is_pick = item.get("is_pick") if isinstance(item.get("is_pick"), bool) else None
        hero_id = _int(item.get("hero_id"), minimum=1)
        team_code = _int(item.get("team"), maximum=1)
        order = _int(item.get("order"), maximum=255)
        if None in (is_pick, hero_id, team_code, order):
            invalid.append(source_order)
        key = (is_pick, hero_id, team_code, order)
        if key in seen_actions:
            duplicate_actions.append(source_order)
        seen_actions.add(key)
        actions.append(DraftAction(
            source_order=source_order, is_pick=is_pick, hero_id=hero_id, team_code=team_code,
            team=Team.RADIANT if team_code == 0 else Team.DIRE if team_code == 1 else None,
            order=order,
        ))
    order_counts = Counter(action.order for action in actions if action.order is not None)
    duplicate_orders = tuple(sorted(order for order, count in order_counts.items() if count > 1))
    present_orders = set(order_counts)
    missing_orders = tuple(
        order for order in range(max(present_orders) + 1) if order not in present_orders
    ) if present_orders else ()
    clean = not invalid and not duplicate_orders and not duplicate_actions and not missing_orders
    return DraftRawData(
        available=True, actions=tuple(actions), duplicate_orders=duplicate_orders,
        duplicate_actions_source_orders=tuple(duplicate_actions), missing_orders=missing_orders,
        invalid_source_orders=tuple(sorted(set(invalid))),
        completeness=QualityStatus.COMPLETE if clean else QualityStatus.PARTIAL,
    )


def _json_list(value: object) -> tuple[JsonValue, ...] | None:
    return tuple(cast(JsonValue, deepcopy(item)) for item in value) if isinstance(value, list) else None


def _number_list(value: object) -> tuple[tuple[int | float | None, ...] | None, bool]:
    if not isinstance(value, list):
        return None, False
    normalized = tuple(
        item if isinstance(item, (int, float)) and not isinstance(item, bool) else None for item in value
    )
    return normalized, all(item is not None for item in normalized)


def _events(match: Mapping[str, Any]) -> MatchEventRawData:
    objectives = _json_list(match.get("objectives"))
    kills_log = _json_list(match.get("kills_log"))
    teamfights = _json_list(match.get("teamfights"))
    gold, gold_valid = _number_list(match.get("radiant_gold_adv"))
    xp, xp_valid = _number_list(match.get("radiant_xp_adv"))
    source_players = match.get("players")
    player_logs = tuple(sorted((
        PlayerEventLogs(
            player_slot=cast(int, source_player["player_slot"]),
            kills_log=_json_list(source_player.get("kills_log")),
            buyback_log=_json_list(source_player.get("buyback_log")),
            purchase_log=_json_list(source_player.get("purchase_log")),
        ) for source_player in source_players if isinstance(source_player, dict)
    ), key=lambda item: item.player_slot)) if isinstance(source_players, list) else ()
    sections = (objectives, kills_log, teamfights, gold, xp)
    any_available = any(section is not None for section in sections)
    complete = all(section is not None for section in sections) and gold_valid and xp_valid
    return MatchEventRawData(
        objectives=objectives, kills_log=kills_log, teamfights=teamfights,
        radiant_gold_adv=gold, radiant_xp_adv=xp,
        completeness=_quality(complete, any_available),
        buyback_log=_json_list(match.get("buyback_log")),
        purchase_log=_json_list(match.get("purchase_log")),
        player_logs=player_logs,
    )


def _metric(numerator: int | None, denominator: int | None) -> DerivedMetric:
    if numerator is None or denominator is None:
        return DerivedMetric(value=None, status=MetricStatus.INPUTS_MISSING)
    if denominator == 0:
        return DerivedMetric(value=None, status=MetricStatus.DENOMINATOR_ZERO)
    return DerivedMetric(value=round(numerator / denominator, 4), status=MetricStatus.AVAILABLE, decimal_places=4)


def kill_participation_counter_ratio(kills: int | None, assists: int | None,
                                     team_score: int | None) -> float | None:
    """Arithmetic counter ratio, not a verified share of unique team kills.

    Values above one are preserved here; suitability for the performance axis is
    a separate decision made with the evaluator's match-quality requirements.
    """
    if kills is None or assists is None or team_score is None or team_score == 0:
        return None
    return (kills + assists) / team_score


def _participation_counter_metric(kills: int | None, assists: int | None,
                                  team_score: int | None) -> DerivedMetric:
    ratio = kill_participation_counter_ratio(kills, assists, team_score)
    if ratio is not None:
        return DerivedMetric(value=round(ratio, 4), status=MetricStatus.AVAILABLE, decimal_places=4)
    return DerivedMetric(value=None, status=(MetricStatus.DENOMINATOR_ZERO if team_score == 0
                         and kills is not None and assists is not None else MetricStatus.INPUTS_MISSING))


def _derived(players: tuple[PlayerStat, ...], scores: Mapping[Team, int | None]) -> tuple[PlayerDerivedStats, ...]:
    return tuple(
        PlayerDerivedStats(
            player_slot=player.player_slot,
            kda=_metric(
                player.kills + player.assists
                if player.kills is not None and player.assists is not None else None,
                player.deaths,
            ),
            kill_participation=_participation_counter_metric(player.kills, player.assists, scores[player.team]),
        )
        for player in players
    )


def _team_value(match: Mapping[str, Any], team: Team, field: str) -> object:
    prefix = team.value
    direct = match.get(f"{prefix}_{field}")
    nested = match.get(f"{prefix}_team")
    return direct if direct is not None else nested.get(field) if isinstance(nested, dict) else None


def normalize_match_snapshot(
    snapshot: Mapping[str, Any], *, hero_names: Mapping[int, str] | None = None,
) -> NormalizedMatch:
    source_snapshot = deepcopy(dict(snapshot))
    source_version = _int(source_snapshot.get("schema_version"), minimum=1)
    source = source_snapshot.get("source")
    fetched_at = source_snapshot.get("source_fetched_at")
    match = source_snapshot.get("match")
    if source_version is None or not isinstance(source, str) or not source:
        raise MatchNormalizationError("snapshot metadata is invalid")
    if not isinstance(fetched_at, str):
        raise MatchNormalizationError("source_fetched_at is invalid")
    try:
        fetched = datetime.fromisoformat(fetched_at)
    except ValueError as error:
        raise MatchNormalizationError("source_fetched_at is invalid") from error
    if fetched.tzinfo is None or fetched.utcoffset() is None:
        raise MatchNormalizationError("source_fetched_at must contain a timezone")
    if not isinstance(match, dict):
        raise MatchNormalizationError("snapshot match must be an object")
    match_id = _int(match.get("match_id"), minimum=1)
    if match_id is None:
        raise MatchNormalizationError("match_id is invalid")

    names = hero_names or {}
    players = _players(match, names)
    draft = _draft(match.get("picks_bans"))
    events = _events(match)
    radiant_score = _int(match.get("radiant_score"))
    dire_score = _int(match.get("dire_score"))
    radiant_win = match.get("radiant_win")
    winner = (
        Team.RADIANT if radiant_win is True else Team.DIRE if radiant_win is False else None
    )
    summary_values: dict[SummaryField, object] = {
        SummaryField.RADIANT_SCORE: radiant_score,
        SummaryField.DIRE_SCORE: dire_score,
        SummaryField.WINNER: winner,
        SummaryField.DURATION: _int(match.get("duration"), minimum=1),
        SummaryField.START_TIME: _int(match.get("start_time")),
        SummaryField.GAME_MODE: _int(match.get("game_mode")),
        SummaryField.LOBBY_TYPE: _int(match.get("lobby_type")),
        SummaryField.PATCH: _int(match.get("patch")),
        SummaryField.RADIANT_TEAM_ID: _id(_team_value(match, Team.RADIANT, "team_id")),
        SummaryField.DIRE_TEAM_ID: _id(_team_value(match, Team.DIRE, "team_id")),
        SummaryField.RADIANT_NAME: _team_value(match, Team.RADIANT, "name") if isinstance(_team_value(match, Team.RADIANT, "name"), str) else None,
        SummaryField.DIRE_NAME: _team_value(match, Team.DIRE, "name") if isinstance(_team_value(match, Team.DIRE, "name"), str) else None,
    }
    available_summary = tuple(field for field in SummaryField if summary_values[field] is not None)
    required_summary = {
        SummaryField.RADIANT_SCORE, SummaryField.DIRE_SCORE, SummaryField.WINNER,
        SummaryField.DURATION, SummaryField.START_TIME, SummaryField.GAME_MODE,
        SummaryField.LOBBY_TYPE, SummaryField.PATCH,
    }
    summary_complete = required_summary.issubset(available_summary) and len(players) == 10 and all(
        player.hero_id is not None for player in players
    )
    stats_complete = len(players) == 10 and all(
        set(CORE_PLAYER_FIELDS).issubset(player.available_fields) for player in players
    )
    roles_confirmed = sum(player.position.evidence == EvidenceStatus.CONFIRMED for player in players)
    quality = DataQuality(
        summary=_quality(summary_complete, bool(available_summary)),
        stats=_quality(stats_complete, bool(players)),
        draft_order=draft.completeness,
        timeline=events.completeness,
        roles=_quality(bool(players) and roles_confirmed == len(players), roles_confirmed > 0),
    )
    roster = tuple(HeroRosterEntry(
        team=player.team, player_slot=player.player_slot,
        hero_id=player.hero_id, hero_name=player.hero_name,
    ) for player in players)
    summary = MatchSummary(
        match_id=str(match_id),
        radiant=TeamSummary(
            team=Team.RADIANT,
            team_id=cast(str | None, summary_values[SummaryField.RADIANT_TEAM_ID]),
            name=cast(str | None, summary_values[SummaryField.RADIANT_NAME]),
            score=radiant_score,
        ),
        dire=TeamSummary(
            team=Team.DIRE,
            team_id=cast(str | None, summary_values[SummaryField.DIRE_TEAM_ID]),
            name=cast(str | None, summary_values[SummaryField.DIRE_NAME]),
            score=dire_score,
        ),
        winner=winner,
        duration=cast(int | None, summary_values[SummaryField.DURATION]),
        start_time=cast(int | None, summary_values[SummaryField.START_TIME]),
        game_mode=cast(int | None, summary_values[SummaryField.GAME_MODE]),
        lobby_type=cast(int | None, summary_values[SummaryField.LOBBY_TYPE]),
        patch=cast(int | None, summary_values[SummaryField.PATCH]),
        hero_roster=roster, available_fields=available_summary,
        data_quality=quality, source_version=source_version,
    )
    status = source_snapshot.get("status")
    return NormalizedMatch(
        source=source, source_fetched_at=fetched, summary=summary, players=players,
        raw=NormalizedRawData(draft=draft, events=events),
        derived=_derived(players, {Team.RADIANT: radiant_score, Team.DIRE: dire_score}),
        source_status=status if isinstance(status, str) and status in {"FOUND_FULL", "FOUND_PARTIAL"} else None,
    )
