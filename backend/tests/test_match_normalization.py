from copy import deepcopy
from typing import Any

import pytest

from app.models.matches import (
    EvidenceStatus,
    MetricStatus,
    PlayerField,
    Position,
    QualityStatus,
    SummaryField,
    Team,
)
from app.services.match_normalization import MatchNormalizationError, normalize_match_snapshot
from app.services.match_analysis import public_base

MATCH_ID = 9223372036854775807


def player(slot: int, hero_id: int) -> dict[str, Any]:
    return {
        "player_slot": slot,
        "hero_id": hero_id,
        "account_id": 4_294_967_000 + slot,
        "steam_id": 18_446_744_073_709_000_000 + slot,
        "kills": 0 if slot == 0 else 5,
        "deaths": 0 if slot == 0 else 2,
        "assists": 7,
        "last_hits": 120,
        "denies": 5,
        "gold_per_min": 500,
        "xp_per_min": 600,
        "hero_damage": 15_000,
        "tower_damage": 2_000,
        "hero_healing": 0,
        "net_worth": 18_000,
        "lane_role": 1 + (slot % 4),
        **{f"item_{index}": index + 1 for index in range(6)},
        "item_neutral": 42,
        "purchase_time": {"blink": [800, 1600], "boots": 120},
    }


def full_snapshot() -> dict[str, Any]:
    players = [player(slot, slot + 1) for slot in range(5)]
    players += [player(128 + index, 100 + index) for index in range(5)]
    return {
        "schema_version": 1,
        "source": "opendota",
        "source_fetched_at": "2026-10-22T11:00:00+00:00",
        "status": "FOUND_FULL",
        "presence": {},
        "match": {
            "match_id": MATCH_ID,
            "duration": 2400,
            "start_time": 1_700_000_000,
            "patch": 55,
            "game_mode": 22,
            "lobby_type": 7,
            "radiant_win": True,
            "radiant_score": 30,
            "dire_score": 20,
            "radiant_team_id": 9_000_000_000_000_001,
            "dire_team": {"team_id": 9_000_000_000_000_002, "name": "Dire Fixture"},
            "radiant_name": "Radiant Fixture",
            "players": players,
            "picks_bans": [
                {"is_pick": True, "hero_id": 1, "team": 0, "order": 0},
                {"is_pick": False, "hero_id": 2, "team": 1, "order": 1},
            ],
            "objectives": [{"type": "CHAT_MESSAGE_FIRSTBLOOD", "time": 10}],
            "kills_log": [{"time": 10, "key": "npc_dota_hero_fixture"}],
            "teamfights": [],
            "radiant_gold_adv": [0, 100, -50],
            "radiant_xp_adv": [0, 120, -25],
        },
    }


def test_full_match_creates_summary_ten_players_raw_and_derived() -> None:
    normalized = normalize_match_snapshot(full_snapshot(), hero_names={1: "Anti-Mage"})
    assert normalized.summary.match_id == str(MATCH_ID)
    assert normalized.summary.winner == Team.RADIANT
    assert normalized.summary.radiant.team_id == "9000000000000001"
    assert normalized.summary.dire.name == "Dire Fixture"
    assert len(normalized.players) == 10 and len(normalized.summary.hero_roster) == 10
    assert [item.team_player_number for item in normalized.players[:5]] == [1, 2, 3, 4, 5]
    assert [item.team for item in normalized.players[5:]] == [Team.DIRE] * 5
    assert normalized.players[0].hero_name == "Anti-Mage"
    assert normalized.players[1].hero_name is None  # Constants resolution is separate and explicit.
    assert normalized.players[0].steam_id == "18446744073709000000"
    assert normalized.players[0].items == (1, 2, 3, 4, 5, 6)
    assert normalized.players[0].item_timings == {"blink": (800, 1600), "boots": (120,)}
    assert normalized.summary.data_quality.summary == QualityStatus.COMPLETE
    assert normalized.summary.data_quality.stats == QualityStatus.COMPLETE
    assert normalized.summary.data_quality.draft_order == QualityStatus.COMPLETE
    assert normalized.summary.data_quality.timeline == QualityStatus.COMPLETE
    assert normalized.derived[0].kda.status == MetricStatus.DENOMINATOR_ZERO
    assert normalized.derived[0].kda.value is None
    assert normalized.derived[0].kill_participation.value == pytest.approx(0.2333)


def test_partial_match_keeps_zero_and_marks_unknown_as_unavailable() -> None:
    snapshot = full_snapshot()
    match = snapshot["match"]
    assert isinstance(match, dict)
    match["patch"] = None
    match["dire_score"] = None
    match["picks_bans"] = None
    match.pop("teamfights")
    match.pop("kills_log")
    players = match["players"]
    assert isinstance(players, list)
    players[:] = players[:2]
    players[0].pop("account_id")
    players[0].pop("hero_id")
    players[0]["kills"] = 0
    players[0].pop("deaths")

    normalized = normalize_match_snapshot(snapshot)
    first = normalized.players[0]
    assert first.kills == 0 and PlayerField.KILLS in first.available_fields
    assert first.deaths is None and PlayerField.DEATHS not in first.available_fields
    assert first.account_id is None and first.hero_id is None
    assert SummaryField.PATCH not in normalized.summary.available_fields
    assert normalized.summary.data_quality.summary == QualityStatus.PARTIAL
    assert normalized.summary.data_quality.stats == QualityStatus.PARTIAL
    assert normalized.summary.data_quality.draft_order == QualityStatus.UNAVAILABLE
    assert normalized.summary.data_quality.timeline == QualityStatus.PARTIAL
    assert normalized.derived[0].kda.status == MetricStatus.INPUTS_MISSING
    assert normalized.derived[0].kill_participation.status == MetricStatus.AVAILABLE


@pytest.mark.parametrize("players", [
    [player(0, 1), player(0, 2)],
    [player(-1, 1)],
    [player(256, 1)],
    [*map(lambda index: player(index, index + 1), range(6))],
])
def test_invalid_or_duplicate_player_slots_are_rejected(players: list[dict[str, Any]]) -> None:
    snapshot = full_snapshot()
    snapshot["match"]["players"] = players
    with pytest.raises(MatchNormalizationError, match="player_slot|team"):
        normalize_match_snapshot(snapshot)


def test_unknown_hero_and_fallback_names_do_not_invent_pick_order() -> None:
    snapshot = full_snapshot()
    players = snapshot["match"]["players"]
    players[0]["hero_id"] = 999_999
    normalized = normalize_match_snapshot(snapshot, hero_names={1: "Known only"})
    first = normalized.players[0]
    assert first.hero_id == 999_999 and first.hero_name is None
    assert first.display_name == "Анонимный игрок"
    assert normalized.raw.draft.actions[0].source_order == 0
    assert normalized.raw.draft.actions[0].hero_id == 1
    assert normalized.raw.draft.actions[0].source_order != first.player_slot + 1


def test_public_nickname_is_used_only_when_present() -> None:
    snapshot = full_snapshot()
    snapshot["match"]["players"][0]["personaname"] = "  Known  Player  "
    snapshot["match"]["players"][1]["personaname"] = "   "
    players = normalize_match_snapshot(snapshot).players
    assert players[0].display_name == "Known Player"
    assert players[0].name_source == 'opendota' and players[0].is_anonymous is False
    assert players[1].display_name == "Анонимный игрок"
    assert players[1].name_source is None and players[1].is_anonymous is True


def test_parsed_player_fields_preserve_zero_and_reject_invalid_values() -> None:
    snapshot = full_snapshot()
    first, second = snapshot['match']['players'][:2]
    first.update(level=30, stuns=0.0, buyback_count=0, backpack_0=0,
                 backpack_1=1, backpack_2=999999, position_est=1)
    second.update(level=0, stuns=float('nan'), buyback_count=-1, backpack_0=None,
                  backpack_1=0, backpack_2=0)
    players = normalize_match_snapshot(snapshot).players
    assert players[0].level == 30
    assert players[0].stun_duration_seconds == 0.0
    assert players[0].buyback_count == 0
    assert players[0].backpack_items == (0, 1, 999999)
    assert players[0].performance_position.position == 1
    assert players[0].performance_position.evidence == EvidenceStatus.ESTIMATED
    assert players[1].level is None and players[1].stun_duration_seconds is None
    assert players[1].buyback_count is None and players[1].backpack_items == (None, 0, 0)
    assert PlayerField.STUN_DURATION_SECONDS in players[0].available_fields
    assert PlayerField.STUN_DURATION_SECONDS not in players[1].available_fields


def test_public_inventory_distinguishes_empty_unknown_and_missing_without_changing_raw_ids() -> None:
    snapshot = full_snapshot()
    first = snapshot['match']['players'][0]
    first['hero_id'] = 999999
    first['item_0'] = 0
    first['item_1'] = 999999
    first.pop('item_2')
    first['item_neutral'] = 0
    first.update(backpack_0=0, backpack_1=1, backpack_2=999999)
    _, report = public_base(normalize_match_snapshot(snapshot, hero_names={1: 'Anti-Mage'}))
    player = report.players[0]
    assert player.hero_id == 999999 and player.hero_name is None and player.hero_image_url is None
    assert player.items[:3] == (0, 999999, None)
    details = player.item_details
    backpack = player.backpack_item_details
    assert details is not None and backpack is not None
    assert details[0] is not None and details[0].status == 'empty'
    assert details[1] is not None and details[1].status == 'unmapped'
    assert details[2] is None
    assert player.neutral_item_details is not None and player.neutral_item_details.status == 'empty'
    assert all(item is not None for item in backpack)
    assert [item.status for item in backpack if item is not None] == ['empty', 'known', 'unmapped']
    assert report.limitations


def test_player_lane_limitation_matches_actual_unknown_count() -> None:
    snapshot = full_snapshot()
    players = snapshot['match']['players']
    lane_note_all = 'Линии всех игроков не подтверждены данными матча.'
    lane_note_some = 'Линия части игроков не подтверждена данными матча.'

    _, full_report = public_base(normalize_match_snapshot(snapshot))
    assert lane_note_all not in full_report.limitations
    assert lane_note_some not in full_report.limitations

    players[0].pop('lane_role')
    _, partial_report = public_base(normalize_match_snapshot(snapshot))
    assert lane_note_some in partial_report.limitations
    assert lane_note_all not in partial_report.limitations

    for player in players[1:]:
        player.pop('lane_role')
    _, unknown_report = public_base(normalize_match_snapshot(snapshot))
    assert lane_note_all in unknown_report.limitations
    assert lane_note_some not in unknown_report.limitations


def test_bad_draft_order_records_source_without_reconstruction() -> None:
    snapshot = full_snapshot()
    snapshot["match"]["picks_bans"] = [
        {"is_pick": True, "hero_id": 1, "team": 0, "order": 0},
        {"is_pick": True, "hero_id": 1, "team": 0, "order": 0},
        {"is_pick": False, "hero_id": 2, "team": 1, "order": 3},
        {"is_pick": "yes", "hero_id": 3, "team": 1, "order": "4"},
    ]
    draft = normalize_match_snapshot(snapshot).raw.draft
    assert draft.completeness == QualityStatus.PARTIAL
    assert draft.duplicate_orders == (0,)
    assert draft.duplicate_actions_source_orders == (1,)
    assert draft.missing_orders == (1, 2)
    assert draft.invalid_source_orders == (3,)
    assert [action.source_order for action in draft.actions] == [0, 1, 2, 3]
    assert draft.actions[3].is_pick is None and draft.actions[3].order is None


def test_absent_teamfight_log_and_invalid_advantage_are_partial() -> None:
    snapshot = full_snapshot()
    snapshot["match"].pop("teamfights")
    snapshot["match"]["radiant_gold_adv"] = [0, "unknown", 50]
    events = normalize_match_snapshot(snapshot).raw.events
    assert events.teamfights is None
    assert events.radiant_gold_adv == (0, None, 50)
    assert events.completeness == QualityStatus.PARTIAL


def test_role_is_unknown_without_evidence_and_not_estimated() -> None:
    snapshot = full_snapshot()
    snapshot["match"]["players"][0].pop("lane_role")
    position = normalize_match_snapshot(snapshot).players[0].position
    assert position.position == Position.UNKNOWN
    assert position.evidence == EvidenceStatus.UNKNOWN
    assert position.confidence is None


def test_normalization_is_deterministic_json_and_does_not_mutate_snapshot() -> None:
    snapshot = full_snapshot()
    original = deepcopy(snapshot)
    first = normalize_match_snapshot(snapshot)
    second = normalize_match_snapshot(snapshot)
    assert snapshot == original
    assert first.model_dump_json() == second.model_dump_json()
    dumped = first.model_dump(mode="json")
    assert dumped["summary"]["match_id"] == str(MATCH_ID)
    assert dumped["players"][0]["account_id"] == "4294967000"
