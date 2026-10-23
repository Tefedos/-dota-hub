import hashlib
import json
from typing import Literal

from app.integrations.opendota_matchups import MatchupBatch, MatchupStat, OpenDotaMatchups
from app.models.draft import DraftReport, Evaluation, LaterInfluence, PickEvaluation, PickVisibility, Reason, TeamDraftScore
from app.models.matches import DraftAction, NormalizedMatch, Team
from app.services.draft.config import DraftConfig, default_config
from app.services.draft.scoring import insufficient, matchup, score_context, applicable_profiles
from app.services.draft.visibility import resolve_sequence


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def analyze_draft(match: NormalizedMatch, *, config: DraftConfig | None = None,
                  matchups: tuple[MatchupBatch, ...] = ()) -> DraftReport:
    config = config or default_config()
    sequence = resolve_sequence(match, config)
    stats: dict[tuple[int, int], MatchupStat] = {}
    batch_ids: set[int] = set()
    for batch in matchups:
        if batch.hero_id in batch_ids:
            raise ValueError('duplicate matchup batch')
        batch_ids.add(batch.hero_id)
        if batch.status == 'ok':
            for row in batch.rows:
                if row.hero_id != batch.hero_id or (row.hero_id, row.opponent_id) in stats:
                    raise ValueError('conflicting matchup identity')
                stats[(row.hero_id, row.opponent_id)] = row
    # No reads of winner, score, kills, deaths, items, gold, duration, or observed lane_role.
    rosters = {team: tuple(p.hero_id for p in sorted(match.players, key=lambda p: p.player_slot)
                           if p.team == team and p.hero_id is not None) for team in Team}
    roster_valid = len(match.players) == 10 and all(len(rosters[t]) == 5 for t in Team) and len(set(rosters[Team.RADIANT] + rosters[Team.DIRE])) == 10
    unavailable = Evaluation(reasons=(insufficient(),))
    teams: dict[Team, TeamDraftScore] = {}
    for team in Team:
        enemy = Team.DIRE if team == Team.RADIANT else Team.RADIANT
        result = score_context(rosters[team], rosters[enemy], match.summary.patch, stats, config, complete=roster_valid)
        evaluation = result.evaluation if roster_valid else result.evaluation.model_copy(update={
            'score': None, 'grade': None, 'confidence': 'low', 'reasons': (*result.evaluation.reasons, insufficient('incomplete_roster'), insufficient()),
        })
        teams[team] = TeamDraftScore(team=team, evaluation=evaluation, breakdown=result.breakdown,
            team_win_conditions=tuple(r.text for r in evaluation.reasons if r.code in {'composition_objectives', 'composition_lategame', 'composition_midgame'} and r.polarity == 'positive'),
            likely_vulnerabilities=tuple(dict.fromkeys(r.text for r in evaluation.reasons if r.polarity == 'negative' or r.code == 'conditional_farm_conflict'))[:4])
    events: list[PickEvaluation] = []
    event_inputs: list[tuple[Team, int | None, DraftAction | None]]
    if sequence.sequential:
        event_inputs = [(a.team, a.hero_id, a) for a in sequence.actions if a.is_pick and a.team is not None]
    else:
        event_inputs = [(p.team, p.hero_id, None) for p in sorted(match.players, key=lambda p: (p.team.value, p.player_slot))]
    profiles = applicable_profiles(config, match.summary.patch)
    hero_names = {descriptor.hero_id: descriptor.name for descriptor in config.catalog}
    for team, hero, action in event_inputs:
        enemy_team = Team.DIRE if team == Team.RADIANT else Team.RADIANT
        view = sequence.visibility[action.source_order] if action is not None else PickVisibility()
        if hero is None:
            final = None
            at_pick = Evaluation(reasons=(Reason(code='sequence_unavailable', kind='limitation', polarity='neutral', scope='data',
                text='Порядок и видимость пиков не подтверждены: оценка на момент выбора недоступна.'),)) if action is None else unavailable
        else:
            final = score_context(rosters[team], rosters[enemy_team], match.summary.patch, stats, config,
                                  focus=hero, complete=roster_valid)
            at_pick = unavailable
            if action is not None:
                at_pick = score_context((*view.own_known_picks_before, hero), view.enemy_revealed_before,
                                        match.summary.patch, stats, config, focus=hero,
                                        complete=len(view.own_known_picks_before) == 4).evaluation
        final_eval = final.evaluation if final is not None else unavailable
        if not roster_valid:
            final_eval = final_eval.model_copy(update={'score': None, 'grade': None, 'confidence': 'low',
                                                       'reasons': (*final_eval.reasons, insufficient())})
        later: list[LaterInfluence] = []
        if action is not None and hero is not None:
            for other in sequence.actions:
                if not other.is_pick or other.team == team or other.hero_id is None or other.order is None or action.order is None:
                    continue
                other_view = sequence.visibility[other.source_order]
                if other.order <= action.order or (view.stage_index is not None and other_view.stage_index == view.stage_index):
                    continue
                _, later_reasons = matchup(hero, other.hero_id, profiles, match.summary.patch, stats, config)
                influences = tuple(r for r in later_reasons if r.polarity != 'neutral')
                if not influences:
                    continue
                # Isolated counterfactual: same final allies/enemies, remove only this later hero.
                without = score_context(rosters[team], tuple(h for h in rosters[enemy_team] if h != other.hero_id),
                                        match.summary.patch, stats, config, focus=hero, complete=roster_valid).evaluation.score
                delta = round(final_eval.score - without, 1) if final_eval.score is not None and without is not None else None
                later.append(LaterInfluence(hero_id=other.hero_id, action_order=other.order, score_delta=delta, reasons=influences))
        reasons = final_eval.reasons
        events.append(PickEvaluation(
            hero_id=hero, hero_name=hero_names.get(hero) if hero is not None else None,
            team=team, action_order=action.order if action else None,
            source_order=action.source_order if action else None, stage=view.stage_index, visibility=view,
            at_pick=at_pick, final_context=final_eval, at_pick_score=at_pick.score, final_score=final_eval.score,
            post_pick_delta=round(final_eval.score - at_pick.score, 1) if final_eval.score is not None and at_pick.score is not None else None,
            later_revealed_counters=tuple(later), countered_heroes=final.countered if final else (),
            threatened_by_heroes=final.threatened if final else (),
            ally_synergies=tuple(r for r in reasons if r.kind == 'mechanic' and r.code in {rule.code for rule in config.rules if rule.kind == 'synergy'}),
            resource_warnings=tuple(r for r in reasons if r.code == 'conditional_farm_conflict'),
            pros=tuple(dict.fromkeys(r.text for r in reasons if r.polarity == 'positive' and r.scope in {'individual', 'interaction'}
                                      and r.patch_applicability == f'exact_patch:{match.summary.patch}'))[:2],
            cons=tuple(dict.fromkeys(r.text for r in reasons if r.polarity == 'negative' and r.scope in {'individual', 'interaction'}
                                      and r.patch_applicability == f'exact_patch:{match.summary.patch}'))[:2],
        ))
    radiant = teams[Team.RADIANT].evaluation.score
    dire = teams[Team.DIRE].evaluation.score
    advantage: Literal['Radiant', 'Dire', 'approximately_even', 'insufficient_data'] = 'insufficient_data'
    # Comparison only meaningful with identical supported axes and full rosters.
    same_axes = {k for k, v in teams[Team.RADIANT].evaluation.axes.items() if v is not None} == {k for k, v in teams[Team.DIRE].evaluation.axes.items() if v is not None}
    if radiant is not None and dire is not None and same_axes:
        advantage = 'approximately_even' if abs(radiant - dire) <= config.even_margin else 'Radiant' if radiant > dire else 'Dire'
    limitations = [
        'Баллы — гипотеза полезности v1, не вероятность победы; веса и правила не откалиброваны.',
        'Статистика матчапов не гарантирует соответствия патчу, позиции или уровню игроков.',
        'Позиции 1–5 не подтверждены. Сила линий и экономика численно не оцениваются.',
        'Справочник механик покрывает только явно перечисленные герои и патчи; отсутствие правила не доказывает отсутствие взаимодействия.',
    ]
    if not sequence.sequential:
        limitations.append('Порядок или видимость не подтверждены: доступны только финальные составы, at_pick отсутствует.')
    if not matchups:
        limitations.append('Статистика матчапов не запрашивалась; она не заменена нейтральным баллом.')
    elif any(b.status != 'ok' for b in matchups):
        limitations.append('Часть запросов статистики матчапов не завершилась успешно; неизвестные пары оставлены без оценки.')
    if any(p.final_context.axes['matchup'] is None for p in events):
        limitations.append('Для части героев нет полной статистики по всем известным соперникам с достаточной выборкой; ось matchup может быть null.')
    if not any(match.summary.patch in p.verified_numeric_patches for p in config.profiles):
        limitations.append('Механические профили не имеют подтверждённой численной применимости к патчу этого матча; их описания не повышают балл.')
    return DraftReport(
        match_id=match.summary.match_id, patch=match.summary.patch,
        mode='SEQUENTIAL' if sequence.sequential else 'FINAL_ONLY', visibility_policy=sequence.policy,
        source_quality=sequence.issues, actions=sequence.actions, pick_events=tuple(events), teams=teams,
        draft_advantage=advantage, model_version=config.model_version,
        config_digest=_digest(config.model_dump(mode='json')),
        evidence_digest=_digest([b.model_dump(mode='json') for b in sorted(matchups, key=lambda b: b.hero_id)]),
        evidence_coverage=round(sum(p.final_context.evidence_coverage for p in events) / len(events), 4) if events else 0.,
        limitations=tuple(limitations),
    )


async def analyze_with_matchups(match: NormalizedMatch, provider: OpenDotaMatchups,
                                *, config: DraftConfig | None = None) -> DraftReport:
    """Explicit opt-in I/O for a bot/FastAPI caller. Max ten distinct heroes, serial budget."""
    batches = []
    for hero in sorted({p.hero_id for p in match.players if p.hero_id is not None})[:10]:
        if not 0 < hero < 100000:
            batches.append(MatchupBatch(hero_id=hero, status='malformed'))
            continue
        batch = await provider.fetch(hero)
        batches.append(batch)
        if batch.status == 'rate_limited':
            break
    return analyze_draft(match, config=config, matchups=tuple(batches))
