"""Overview contracts from stored, normalized match snapshots."""
import json
from pathlib import Path

import pytest

from app.models.match_api import OverviewReport
from app.services.match_analysis import public_base
from app.services.match_normalization import normalize_match_snapshot
from app.services.player_catalog import hero_catalog, match_metadata_catalog
from test_match_normalization import full_snapshot

FIXTURES = Path(__file__).parent / 'fixtures'
HERO_NAMES = {hero_id: row['name'] for hero_id, row in hero_catalog()[1].items()}


@pytest.mark.parametrize('relative,expected_id', [
    ('timeline/9051271323.json', '9051271323'),
    ('draft/independent.json', '1000000001'),
])
def test_existing_match_fixtures_keep_real_roster(relative: str, expected_id: str) -> None:
    snapshot = json.loads((FIXTURES / relative).read_text())
    normalized = normalize_match_snapshot(snapshot, hero_names=HERO_NAMES)
    overview, _ = public_base(normalized)
    assert overview.match_id == expected_id
    assert len(overview.radiant.players) == len(overview.dire.players) == 5
    assert [p.player_slot for p in overview.radiant.players] == sorted(p.player_slot for p in overview.radiant.players)
    assert [p.player_slot for p in overview.dire.players] == sorted(p.player_slot for p in overview.dire.players)
    assert {p.hero_id for p in overview.radiant.players + overview.dire.players} == {
        p['hero_id'] for p in snapshot['match']['players']
    }
    assert overview.team_stats.radiant.kills == overview.radiant.score  # type: ignore[union-attr]
    assert overview.team_stats.dire.kills == overview.dire.score  # type: ignore[union-attr]
    assert overview.team_stats.radiant.towers_destroyed is None  # type: ignore[union-attr]
    assert overview.team_stats.dire.roshan_kills is None  # type: ignore[union-attr]
    assert overview.game_mode_name == 'All Draft'
    assert overview.patch_name == '7.41'


def test_partial_roster_and_unknown_metadata_do_not_invent_values() -> None:
    snapshot = full_snapshot()
    source = snapshot['match']
    source['players'] = [source['players'][0], source['players'][1], source['players'][5]]
    source['players'][0]['hero_id'] = 999999
    source['players'][0].pop('personaname', None)
    source['patch'] = 999
    source['game_mode'] = 999
    normalized = normalize_match_snapshot(snapshot, hero_names=HERO_NAMES)
    overview, _ = public_base(normalized)
    assert len(overview.radiant.players) == 2 and len(overview.dire.players) == 1
    assert overview.radiant.players[0].hero_id == 999999
    assert overview.radiant.players[0].hero_name is None
    assert overview.radiant.players[0].hero_image_url is None
    assert overview.radiant.players[0].display_name is None
    assert overview.patch_name is None and overview.game_mode_name is None
    assert any('неполные' in note for note in overview.limitations)
    assert OverviewReport.model_validate_json(overview.model_dump_json()) == overview


def test_missing_optional_overview_fields_from_old_report_still_parse() -> None:
    normalized = normalize_match_snapshot(full_snapshot(), hero_names=HERO_NAMES)
    overview, _ = public_base(normalized)
    old = overview.model_dump(mode='json')
    for key in ('game_mode_name', 'patch_name', 'team_stats', 'limitations'):
        old.pop(key)
    for team in ('radiant', 'dire'):
        old[team].pop('players')
    restored = OverviewReport.model_validate_json(json.dumps(old))
    assert restored.radiant.players == () and restored.team_stats is None


def test_metadata_catalog_is_pinned_and_unknown_ids_return_none() -> None:
    revision, modes, patches = match_metadata_catalog()
    assert revision == hero_catalog()[0]
    assert modes[22] == 'All Draft' and patches[60] == '7.41'
    assert modes.get(999999) is None and patches.get(999999) is None
