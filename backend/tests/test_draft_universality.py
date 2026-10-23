"""Independent rosters, arbitrary identities and frozen live OpenDota evidence."""
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from app.integrations.opendota_matchups import MatchupBatch
from app.models.matches import Team
from app.services.draft.analyzer import analyze_draft
from app.services.draft.config import DraftConfig, HeroProfile, default_config
from app.services.match_normalization import normalize_match_snapshot
from test_draft_analyzer import fixture_config, fixture_snapshot, stats_for

FIXTURES = Path(__file__).parent / 'fixtures' / 'draft'


def independent_snapshot() -> dict[str, Any]:
    value: dict[str, Any] = json.loads((FIXTURES / 'independent.json').read_text())
    return value


def independent_config() -> DraftConfig:
    # Test-only capability assignments exercise the engine. Not production hero claims.
    tags = {
        2: ('control', 'initiation', 'aoe', 'magical', 'midgame'),
        3: ('save', 'control', 'magical', 'midgame'),
        6: ('physical', 'farm', 'lategame', 'illusions'),
        8: ('physical', 'sustained', 'farm', 'lategame'),
        9: ('mobility', 'control', 'magical', 'objectives', 'midgame'),
        18: ('physical', 'control', 'farm', 'lategame'),
        22: ('magical', 'aoe', 'midgame'),
        26: ('control', 'magical', 'midgame'),
        52: ('objectives', 'magical', 'aoe', 'midgame'),
        54: ('physical', 'sustained', 'farm', 'lategame'),
    }
    profiles = tuple(HeroProfile.model_validate({
        'hero_id': hero, 'name': f'Fixture capabilities {hero}', 'tags': capabilities,
        'patches': (60,), 'verified_numeric_patches': (60,),
        'source_refs': ('fixture://independent-capabilities',),
    }) for hero, capabilities in tags.items())
    return fixture_config().model_copy(update={'profiles': profiles, 'catalog': ()})


def test_independent_ten_heroes_have_descriptors_but_no_invented_mechanics() -> None:
    match = normalize_match_snapshot(independent_snapshot())
    config = default_config()
    assert len(config.catalog) == 127 and len({h.hero_id for h in config.catalog}) == 127
    assert not {p.hero_id for p in match.players} & {p.hero_id for p in config.profiles}
    report = analyze_draft(match, matchups=stats_for(match))
    assert len(report.pick_events) == 10 and report.mode == 'FINAL_ONLY'
    for pick in report.pick_events:
        assert pick.final_score is None and pick.final_context.axes['matchup'] == 50
        assert any(r.code == 'catalog_hero_features' and r.patch_applicability == 'snapshot_unverified'
                   for r in pick.final_context.reasons)
        assert not any(r.kind == 'mechanic' for r in pick.final_context.reasons)
        assert not pick.resource_warnings
    assert all(t.evaluation.score is None for t in report.teams.values())


def test_catalog_is_descriptive_and_cannot_change_scores() -> None:
    match = normalize_match_snapshot(fixture_snapshot())
    config = fixture_config()
    before = analyze_draft(match, config=config, matchups=stats_for(match))
    after = analyze_draft(match, config=config.model_copy(update={'catalog': ()}), matchups=stats_for(match))
    assert [p.final_score for p in before.pick_events] == [p.final_score for p in after.pick_events]
    assert [p.at_pick_score for p in before.pick_events] == [p.at_pick_score for p in after.pick_events]
    assert {t: v.evaluation.axes for t, v in before.teams.items()} == {t: v.evaluation.axes for t, v in after.teams.items()}


def test_independent_profiles_use_same_generic_engine_and_rules_change_scores() -> None:
    match = normalize_match_snapshot(independent_snapshot())
    config = independent_config()
    original = analyze_draft(match, config=config, matchups=stats_for(match))
    changed = config.model_copy(update={'rules': tuple(
        r.model_copy(update={'utility': 40.}) if r.code == 'control_followup' else r for r in config.rules)})
    other = analyze_draft(match, config=changed, matchups=stats_for(match))
    assert original.mode == 'SEQUENTIAL'
    assert sum(p.final_score is not None for p in original.pick_events) == 8
    assert original.teams[Team.RADIANT].evaluation.score != other.teams[Team.RADIANT].evaluation.score
    assert original.config_digest != other.config_digest
    assert any(a.final_score != b.final_score for a, b in zip(original.pick_events, other.pick_events, strict=True))


def test_changed_roster_changes_scores_without_any_outcome_change() -> None:
    before = independent_snapshot()
    after = deepcopy(before)
    for player in after['match']['players']:
        player['hero_id'] = {6: 22, 22: 6}.get(player['hero_id'], player['hero_id'])
    for action in after['match']['picks_bans']:
        action['hero_id'] = {6: 22, 22: 6}.get(action['hero_id'], action['hero_id'])
    a, b = normalize_match_snapshot(before), normalize_match_snapshot(after)
    first = analyze_draft(a, config=independent_config(), matchups=stats_for(a))
    second = analyze_draft(b, config=independent_config(), matchups=stats_for(b))
    assert first.teams[Team.RADIANT].evaluation.score != second.teams[Team.RADIANT].evaluation.score
    assert before['match']['radiant_win'] == after['match']['radiant_win']


def test_renaming_every_hero_id_preserves_all_scores() -> None:
    original = independent_snapshot()
    renamed = deepcopy(original)
    for player in renamed['match']['players']:
        player['hero_id'] += 10000
    for action in renamed['match']['picks_bans']:
        action['hero_id'] += 10000
    config = independent_config()
    renamed_config = config.model_copy(update={'profiles': tuple(
        p.model_copy(update={'hero_id': p.hero_id + 10000}) for p in config.profiles)})
    a, b = normalize_match_snapshot(original), normalize_match_snapshot(renamed)
    first = analyze_draft(a, config=config, matchups=stats_for(a))
    second = analyze_draft(b, config=renamed_config, matchups=stats_for(b))
    assert [p.final_score for p in first.pick_events] == [p.final_score for p in second.pick_events]
    assert [p.at_pick_score for p in first.pick_events] == [p.at_pick_score for p in second.pick_events]
    assert {t: v.evaluation.axes for t, v in first.teams.items()} == {t: v.evaluation.axes for t, v in second.teams.items()}


@pytest.mark.parametrize('snapshot_factory', [fixture_snapshot, independent_snapshot])
def test_match_id_is_only_report_identity(snapshot_factory: Any) -> None:
    snapshot = snapshot_factory()
    config = fixture_config() if snapshot_factory == fixture_snapshot else independent_config()
    a = normalize_match_snapshot(snapshot)
    snapshot['match']['match_id'] = 42
    b = normalize_match_snapshot(snapshot)
    first = analyze_draft(a, config=config, matchups=stats_for(a))
    second = analyze_draft(b, config=config, matchups=stats_for(b))
    assert first.model_dump(exclude={'match_id'}) == second.model_dump(exclude={'match_id'})


def test_independent_partial_picks_keep_final_analysis() -> None:
    snapshot = independent_snapshot()
    match = normalize_match_snapshot(snapshot)
    before = analyze_draft(match, config=independent_config(), matchups=stats_for(match))
    snapshot['match']['picks_bans'] = snapshot['match']['picks_bans'][:3]
    after = analyze_draft(normalize_match_snapshot(snapshot), config=independent_config(), matchups=stats_for(match))
    assert after.mode == 'FINAL_ONLY' and len(after.actions) == 3 and len(after.pick_events) == 10
    assert after.teams == before.teams
    assert {p.hero_id: p.final_context for p in after.pick_events} == {p.hero_id: p.final_context for p in before.pick_events}
    assert all(p.at_pick_score is None and p.action_order is None and p.stage is None for p in after.pick_events)


def test_inconsistent_team_code_rejects_sequence() -> None:
    match = normalize_match_snapshot(fixture_snapshot())
    actions = list(match.raw.draft.actions)
    actions[0] = actions[0].model_copy(update={'team_code': 1})
    draft = match.raw.draft.model_copy(update={'actions': tuple(actions)})
    match = match.model_copy(update={'raw': match.raw.model_copy(update={'draft': draft})})
    report = analyze_draft(match, config=fixture_config())
    assert report.mode == 'FINAL_ONLY' and 'inconsistent_team_code' in report.source_quality


def test_real_match_replay_preserves_invalid_picks_and_never_invents_stages() -> None:
    evidence = json.loads((FIXTURES / '9051271323' / 'evidence.json').read_text())
    batches = tuple(MatchupBatch.model_validate_json(json.dumps(b)) for b in evidence['matchups'])
    match = normalize_match_snapshot(evidence['snapshot'])
    report = analyze_draft(match, matchups=batches)
    assert report.match_id == '9051271323' and report.patch == 60
    assert report.mode == 'FINAL_ONLY' and len(report.pick_events) == 10
    assert len(report.actions) == 16 and sum(a.is_pick is True for a in report.actions) == 11
    assert 'picks_roster_mismatch' in report.source_quality
    assert 14 not in {p.hero_id for p in report.pick_events}
    assert any(a.hero_id == 14 and a.is_pick for a in report.actions)
    assert all(p.at_pick_score is None and p.stage is None and not p.later_revealed_counters for p in report.pick_events)
    assert report.teams[Team.DIRE].evaluation.score is None
    assert report.draft_advantage == 'insufficient_data'
    # Real result and player performance are irrelevant too, with frozen statistical evidence.
    changed = deepcopy(evidence['snapshot'])
    changed['match'].update(radiant_win=not changed['match']['radiant_win'], radiant_score=999, dire_score=0)
    for player in changed['match']['players']:
        player.update(kills=777, deaths=888, assists=999)
    assert report == analyze_draft(normalize_match_snapshot(changed), matchups=batches)
