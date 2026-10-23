import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.models.matches import QualityStatus, Team
from app.services.match_normalization import normalize_match_snapshot
from app.services.timeline import analyze_timeline, filter_timeline_events

REAL_FIXTURE = Path(__file__).parent / "fixtures/timeline/9051271323.json"


def snapshot() -> dict[str, Any]:
    return {
        "schema_version": 1, "source": "opendota", "status": "FOUND_FULL",
        "source_fetched_at": "2026-10-22T00:00:00+00:00",
        "match": {
            "match_id": 123, "duration": 1200,
            "players": [{"player_slot": 0, "hero_id": 1,
                         "kills_log": [{"time": 100, "key": "npc_dota_hero_axe"}],
                         "buyback_log": [{"time": 470, "type": "buyback_log"}],
                         "purchase_log": [{"time": -29, "key": "tango"}]},
                        {"player_slot": 128, "hero_id": 2}],
            "objectives": [{"time": 100, "type": "CHAT_MESSAGE_FIRSTBLOOD", "player_slot": 0},
                           {"time": 300, "type": "building_kill", "key": "npc_dota_badguys_tower1_mid"},
                           {"time": 400, "type": "CHAT_MESSAGE_ROSHAN_KILL"}],
            "teamfights": [{"start": 90, "end": 120, "deaths": 2, "players": [{"buybacks": 0}, {"buybacks": 1}]}],
            "radiant_gold_adv": [0, 100, 100, 3500, 4000],
            "radiant_xp_adv": [0, 50, 100, 4100, 4300],
        },
    }


def report(data: dict[str, Any] | None = None) -> Any:
    return analyze_timeline(normalize_match_snapshot(data if data is not None else snapshot()))


def test_full_match_chronology_evidence_and_turning_point() -> None:
    result = report()
    assert result.quality == QualityStatus.COMPLETE and result.event_coverage == 1
    assert [e.time_start for e in result.events] == sorted(e.time_start for e in result.events)
    assert result.events[0].display_clock == "-0:29"
    assert result.events[0].type == "purchase"
    assert len(result.turning_points) == 1
    point = result.turning_points[0]
    assert point.direction == Team.RADIANT and point.confidence == "medium"
    assert point.time_start == 60 and point.time_end == 240
    assert point.gold_delta == 3900 and point.xp_delta == 4250
    assert point.related_event_ids
    assert "SIGNIFICANT_ADVANTAGE_CHANGE" in point.reason_codes
    fight = next(e for e in result.events if e.type == "teamfight")
    assert fight.time_seconds is None and fight.time_precision == "interval"
    assert fight.evidence["deaths"] == 2 and fight.evidence["buybacks"] == 1
    assert len(fight.related_event_ids) == 1 and fight.actors == ()


def test_partial_without_fights_and_missing_sources() -> None:
    data = snapshot()
    data["status"] = "FOUND_PARTIAL"
    del data["match"]["teamfights"]
    result = report(data)
    assert result.quality == QualityStatus.PARTIAL
    assert "teamfight" in result.missing_event_types
    assert "teamfight" not in result.available_types
    assert result.event_coverage == 0.8571
    assert any("частично" in text for text in result.limitations)


def test_empty_arrays_are_available_but_no_events_or_curves_is_unavailable() -> None:
    data = snapshot()
    data["match"]["objectives"] = []
    data["match"]["teamfights"] = []
    data["match"]["players"] = []
    data["match"]["radiant_gold_adv"] = []
    data["match"]["radiant_xp_adv"] = []
    result = report(data)
    assert result.quality == QualityStatus.UNAVAILABLE
    assert result.events == () and result.turning_points == ()
    assert result.event_coverage == pytest.approx(4 / 7, abs=0.0001)
    assert result.empty_state_text


def test_duplicate_kill_and_fight_are_merged_without_making_extra_kills() -> None:
    data = snapshot()
    player = data["match"]["players"][0]
    player["kills_log"].append(deepcopy(player["kills_log"][0]))
    data["match"]["teamfights"].append(deepcopy(data["match"]["teamfights"][0]))
    result = report(data)
    kills = [e for e in result.events if e.type == "hero_kill"]
    fights = [e for e in result.events if e.type == "teamfight"]
    assert len(kills) == len(fights) == 1
    assert len(kills[0].original_refs) == len(fights[0].original_refs) == 2


def test_malformed_times_actors_and_nullable_entries_are_skipped() -> None:
    data = snapshot()
    data["match"]["objectives"] += [None, {"time": "2:15", "type": "CHAT_MESSAGE_ROSHAN_KILL"},
                                      {"time": 1500, "type": "CHAT_MESSAGE_ROSHAN_KILL"}]
    data["match"]["players"][0]["kills_log"] += [None, {"time": 110, "key": "npc_dota_hero_axe", "player_slot": 999}]
    data["match"]["teamfights"].append({"start": 300, "end": 200})
    result = report(data)
    assert result.quality == QualityStatus.PARTIAL
    assert len([e for e in result.events if e.type == "roshan"]) == 1
    assert len([e for e in result.events if e.type == "hero_kill"]) == 1
    assert any("некорректные" in text for text in result.limitations)


def test_roshan_without_owner_is_not_given_a_team() -> None:
    event = next(e for e in report().events if e.type == "roshan")
    assert event.team is None and event.actors == ()
    assert event.evidence_quality == "partial"


def test_boolean_team_marker_is_not_interpreted_as_radiant() -> None:
    data = snapshot()
    data["match"]["objectives"] = [{"time": 400, "type": "CHAT_MESSAGE_ROSHAN_KILL", "team": False}]
    event = next(e for e in report(data).events if e.type == "roshan")
    assert event.team is None


def test_advantage_signs_and_zero_are_correct() -> None:
    data = snapshot()
    data["match"]["radiant_gold_adv"] = [-100, 0, 100]
    points = report(data).gold_adv_points
    assert [p.advantage_for for p in points] == [Team.DIRE, None, Team.RADIANT]
    assert [p.time_seconds for p in points] == [0, 60, 120]


def test_missing_curves_never_create_a_turning_point() -> None:
    data = snapshot()
    data["match"].pop("radiant_gold_adv")
    data["match"].pop("radiant_xp_adv")
    result = report(data)
    assert result.turning_points == () and result.gold_adv_points == ()
    assert result.quality == QualityStatus.PARTIAL


def test_gap_in_minute_grid_is_not_interpolated() -> None:
    data = snapshot()
    data["match"]["radiant_gold_adv"] = [0, None, 0, 5000]
    data["match"]["radiant_xp_adv"] = []
    assert report(data).turning_points == ()


def test_buyback_and_filters() -> None:
    result = report()
    buyback = next(e for e in result.events if e.type == "buyback")
    assert buyback.team == Team.RADIANT and buyback.actors[0].player_slot == 0
    assert filter_timeline_events(result, event_type="buyback", team=Team.RADIANT) == (buyback,)
    assert filter_timeline_events(result, event_type="buyback", team=Team.DIRE) == ()


def test_miniboss_does_not_become_roshan_and_no_synthesized_fight() -> None:
    data = snapshot()
    data["match"]["objectives"] = [{"time": 400, "type": "CHAT_MESSAGE_MINIBOSS_KILL"}]
    data["match"]["teamfights"] = None
    result = report(data)
    assert not any(e.type in ("roshan", "teamfight") for e in result.events)


def test_deterministic_ids_and_input_is_unchanged() -> None:
    data = snapshot()
    before = deepcopy(data)
    first, second = report(data), report(data)
    assert first == second and data == before


def test_real_match_redacted_projection() -> None:
    data = json.loads(REAL_FIXTURE.read_text())
    result = report(data)
    assert result.match_id == "9051271323" and result.quality == QualityStatus.PARTIAL
    assert len(result.events) > 100 and len(result.gold_adv_points) == 33
    assert len(result.xp_adv_points) == 33 and len(result.turning_points) > 0
    assert "roshan" not in result.available_types  # MINIBOSS is not Roshan.
    assert any(e.type == "buyback" for e in result.events)
