"""Explicit public OpenDota smoke check, or deterministic replay of saved evidence.

Run with the project virtualenv. No secrets, DB writes, Telegram or UI side effects.
"""
import argparse
import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from app.integrations.opendota import OpenDotaClient, parse_match_response  # noqa: E402
from app.integrations.opendota_matchups import MatchupBatch, OpenDotaMatchups  # noqa: E402
from app.services.draft.analyzer import analyze_draft  # noqa: E402
from app.services.match_normalization import normalize_match_snapshot  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('match_id', type=int)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--offline', action='store_true', help='Replay evidence.json without network')
    args = parser.parse_args()
    if not 0 < args.match_id <= 9223372036854775807:
        parser.error('match_id is outside the supported BIGINT range')
    evidence_path = args.output_dir / 'evidence.json'
    if args.offline:
        evidence = json.loads(evidence_path.read_text())
        snapshot = evidence['snapshot']
        if snapshot['match']['match_id'] != args.match_id:
            parser.error('saved match ID differs from requested ID')
        batches = tuple(MatchupBatch.model_validate_json(json.dumps(b)) for b in evidence['matchups'])
    else:
        client = OpenDotaClient(base_url='https://api.opendota.com/api', api_key=None,
                               timeout_seconds=20, max_retries=1, backoff_seconds=1)
        try:
            result = await client.fetch_match(args.match_id)
            if result.snapshot is None:
                raise SystemExit(f'OpenDota match unavailable: {result.status}')
            # Explicit allowlist: retain draft/stats needed for replay, no player identity or chat.
            payload = result.snapshot['match']
            keep = ('match_id', 'duration', 'start_time', 'patch', 'game_mode', 'lobby_type',
                    'radiant_win', 'radiant_score', 'dire_score', 'picks_bans')
            minimal = {k: payload[k] for k in keep if k in payload}
            minimal['players'] = [{k: p[k] for k in ('player_slot', 'hero_id', 'kills', 'deaths', 'assists') if k in p}
                                  for p in payload['players']]
            parsed = parse_match_response(args.match_id, minimal,
                                          datetime.fromisoformat(result.snapshot['source_fetched_at']))
            assert parsed.snapshot is not None
            snapshot = parsed.snapshot
            normalized = normalize_match_snapshot(snapshot)
            heroes = sorted({p.hero_id for p in normalized.players if p.hero_id is not None})
            provider = OpenDotaMatchups(client)
            collected = []
            for hero in heroes[:10]:
                batch = await provider.fetch(hero)
                collected.append(batch.model_copy(update={
                    'rows': tuple(r for r in batch.rows if r.opponent_id in heroes),
                }))
                if batch.status == 'rate_limited':
                    break
                await asyncio.sleep(1)  # Respect the public endpoint's shared request budget.
            batches = tuple(collected)
            evidence = {
                'source_ref': f'https://api.opendota.com/api/matches/{args.match_id}',
                'recorded_at': datetime.now(UTC).isoformat(),
                'note': 'Real public response; identity-free projection. Matchup rows restricted to this roster.',
                'snapshot': snapshot, 'matchups': [b.model_dump(mode='json') for b in batches],
            }
            args.output_dir.mkdir(parents=True, exist_ok=True)
            evidence_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
        finally:
            await client.close()
    report = analyze_draft(normalize_match_snapshot(snapshot), matchups=batches)
    (args.output_dir / 'report.json').write_text(report.model_dump_json(indent=2) + '\n')
    print(json.dumps({
        'match_id': report.match_id, 'mode': report.mode, 'patch': report.patch,
        'source_quality': report.source_quality, 'pick_count': len(report.pick_events),
        'team_scores': {k.value: v.evaluation.score for k, v in report.teams.items()},
        'draft_advantage': report.draft_advantage,
        'matchup_statuses': {b.hero_id: b.status for b in batches},
        'scored_picks': sum(p.final_score is not None for p in report.pick_events),
    }, ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
