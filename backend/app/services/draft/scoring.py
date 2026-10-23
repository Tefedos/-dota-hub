"""Explicit utility hypotheses, source evidence and missing-data gates."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import mean
from typing import Literal

from app.integrations.opendota_matchups import MatchupStat
from app.models.draft import Axis, Evaluation, Reason
from app.services.draft.config import DraftConfig, HeroProfile, LOCAL_RULES


@dataclass(frozen=True)
class ContextScore:
    evaluation: Evaluation
    breakdown: dict[str, float | None]
    countered: tuple[int, ...]
    threatened: tuple[int, ...]


def insufficient(code: str = 'insufficient_data') -> Reason:
    return Reason(code=code, text='Нет оснований для уверенной оценки.', kind='limitation', polarity='neutral')


def aggregate(axes: dict[Axis, float | None], reasons: list[Reason], config: DraftConfig,
              *, allow_score: bool = True) -> Evaluation:
    available = {key: value for key, value in axes.items() if value is not None}
    coverage = sum(config.weights[key] for key in available)
    enough = allow_score and len(available) >= config.minimum_axes and coverage + 1e-9 >= config.minimum_coverage
    score = round(sum(config.weights[k] * v for k, v in available.items()) / coverage, 1) if enough else None
    if score is None:
        reasons = [*reasons, insufficient()]
    elif coverage < 1:
        reasons = [*reasons, Reason(code='partial_evidence', text='Предварительная оценка: не все расчётные оси подтверждены.',
                                    kind='limitation', polarity='neutral', scope='data')]
    grade: Literal['хороший', 'средний', 'спорный', 'неудачный'] | None = None if score is None else 'хороший' if score >= config.grade_boundaries[2] else 'средний' if score >= config.grade_boundaries[1] else 'спорный' if score >= config.grade_boundaries[0] else 'неудачный'
    patch_unknown = any(r.kind == 'statistic' or r.patch_applicability == 'snapshot_unverified' for r in reasons)
    return Evaluation(score=score, grade=grade, confidence='medium' if enough and coverage >= .7 and not patch_unknown else 'low',
                      evidence_coverage=round(coverage, 4), axes=axes, reasons=tuple(reasons))


def applicable_profiles(config: DraftConfig, patch: int | None) -> dict[int, HeroProfile]:
    return {p.hero_id: p for p in config.profiles if patch in p.patches}


def composition(heroes: Sequence[int], profiles: Mapping[int, HeroProfile], *, complete: bool,
                patch: int | None, config: DraftConfig) -> tuple[dict[str, float | None], list[Reason]]:
    """Only observed capabilities can be positive; a partial profile never proves absence."""
    dimensions = ('laning', 'initiation_control', 'damage_mix', 'farm_economy', 'midgame', 'lategame', 'objectives')
    breakdown: dict[str, float | None] = dict.fromkeys(dimensions)
    reasons: list[Reason] = []
    covered = [profiles[h] for h in heroes if h in profiles]
    tags = {tag for profile in covered for tag in profile.tags}
    verified_tags = {tag for profile in covered if patch in profile.verified_numeric_patches for tag in profile.tags}
    refs = tuple(sorted({ref for p in covered for ref in p.source_refs} | {LOCAL_RULES}))
    # Lane roles are post-game observations, not verified pre-pick positions. Do not use them.
    farm = tuple(p.hero_id for p in covered if 'farm' in p.tags)
    if len(farm) >= 2:
        reasons.append(Reason(code='conditional_farm_conflict', kind='composition', polarity='neutral', scope='team', hero_ids=farm,
            text='Если эти герои занимают фармящие позиции, возможна конкуренция за безопасный фарм. Позиции не подтверждены.',
            confidence='low', source_refs=refs, patch_applicability='snapshot_unverified'))
    reasons.append(Reason(code='positions_unverified', kind='limitation', polarity='neutral', scope='team',
                          text='Линии и распределение ресурсов требуют подтверждённых позиций; lane_role этого не доказывает.'))
    criteria: tuple[tuple[str, frozenset[str], str], ...] = (
        ('initiation_control', frozenset(('initiation', 'control')), 'В известных профилях есть средства начала боя и контроля.'),
        ('damage_mix', frozenset(('physical', 'magical')), 'В известных профилях есть физический и магический источники урона.'),
        ('midgame', frozenset(('midgame',)), 'В известных профилях есть инструменты для активной игры в середине матча.'),
        ('lategame', frozenset(('lategame',)), 'В известных профилях есть потенциал затяжной игры при обеспечении ресурсов.'),
        ('objectives', frozenset(('objectives',)), 'В известных профилях есть инструменты давления на строения.'),
    )
    for dimension, required, positive in criteria:
        if required.issubset(tags):
            contributors = tuple(p.hero_id for p in covered if required.intersection(p.tags))
            verified = required.issubset(verified_tags)
            if verified:
                breakdown[dimension] = config.composition_present
            reasons.append(Reason(code=f'composition_{dimension}', kind='composition',
                polarity='positive', scope='team', text=positive, hero_ids=contributors, source_refs=refs, confidence='low',
                patch_applicability=f'exact_patch:{patch}' if verified else 'snapshot_unverified',
                evidence={'utility': config.composition_present} if verified else {}))
    if not complete or len(covered) != len(heroes) or any(patch not in profile.verified_numeric_patches for profile in covered):
        reasons.append(Reason(code='capability_coverage_unknown', kind='limitation', polarity='neutral', scope='team',
            text='Неполное или не подтверждённое для патча покрытие механик не доказывает отсутствие функций у команды.'))
    if 'dispel' in tags:
        reasons.append(Reason(code='dispel_access', text='Есть источник развеивания; его применимость зависит от типа эффекта.',
                              kind='composition', polarity='positive', scope='team',
                              hero_ids=tuple(p.hero_id for p in covered if 'dispel' in p.tags),
                              source_refs=refs, patch_applicability='snapshot_unverified'))
    if 'mobility' in tags:
        reasons.append(Reason(code='mobility_access', text='Есть мобильные герои для смены направления атаки.',
                              kind='composition', polarity='positive', scope='team',
                              hero_ids=tuple(p.hero_id for p in covered if 'mobility' in p.tags),
                              source_refs=refs, patch_applicability='snapshot_unverified'))
    return breakdown, reasons


def matchup(hero: int, enemy: int, profiles: Mapping[int, HeroProfile], patch: int | None,
            statistics: Mapping[tuple[int, int], MatchupStat], config: DraftConfig) -> tuple[float | None, list[Reason]]:
    signals: list[float] = []
    reasons: list[Reason] = []
    row = statistics.get((hero, enemy))
    if row is not None:
        if row.games_played >= config.minimum_matchup_games:
            smoothed = 100 * (row.wins + config.prior_games / 2) / (row.games_played + config.prior_games)
            signals.append(smoothed)
            reasons.append(Reason(code='aggregate_matchup_signal', kind='statistic', scope='interaction',
                polarity='positive' if smoothed > 50 + config.matchup_effect_threshold else 'negative' if smoothed < 50 - config.matchup_effect_threshold else 'neutral',
                hero_ids=(hero, enemy), text='Сглаженная статистика встреч — корреляционный сигнал; патч и позиции выборки неизвестны.',
                source_refs=(row.source_ref,), confidence='low', patch_applicability='aggregate_unknown',
                evidence={'games_played': row.games_played, 'wins': row.wins, 'prior_games': config.prior_games,
                          'smoothed_percent': round(smoothed, 2), 'fetched_at': row.fetched_at.isoformat()}))
        else:
            reasons.append(Reason(code='small_matchup_sample', kind='limitation', polarity='neutral', scope='data', hero_ids=(hero, enemy),
                                  text='Выборка матчапа слишком мала для численной оценки.', source_refs=(row.source_ref,),
                                  evidence={'games_played': row.games_played, 'minimum': config.minimum_matchup_games}))
    if hero in profiles and enemy in profiles:
        for rule in config.rules:
            if rule.kind != 'counter' or patch not in rule.patches:
                continue
            for actor, target, sign in ((hero, enemy, 1), (enemy, hero, -1)):
                if rule.actor_tag in profiles[actor].tags and rule.target_tag in profiles[target].tags:
                    utility = rule.utility if sign == 1 else 100 - rule.utility
                    verified = all(patch in value.verified_numeric_patches for value in (profiles[actor], profiles[target])) and patch in rule.verified_numeric_patches
                    if verified:
                        signals.append(utility)
                    reasons.append(Reason(code=rule.code, text=rule.text, kind='mechanic', scope='interaction',
                        polarity='positive' if sign == 1 else 'negative', hero_ids=(actor, target),
                        confidence='low', source_refs=tuple(sorted(set(rule.source_refs + profiles[actor].source_refs + profiles[target].source_refs))),
                        patch_applicability=f'exact_patch:{patch}' if verified else 'snapshot_unverified',
                        evidence={'utility': utility} if verified else {}))
    return (mean(signals) if signals else None), reasons


def score_context(heroes: tuple[int, ...], enemies: tuple[int, ...], patch: int | None,
                  statistics: Mapping[tuple[int, int], MatchupStat], config: DraftConfig,
                  *, focus: int | None = None, complete: bool = False) -> ContextScore:
    profiles = applicable_profiles(config, patch)
    reasons: list[Reason] = []
    descriptors = {d.hero_id: d for d in config.catalog}
    for hero in ((focus,) if focus is not None else heroes):
        descriptor = descriptors.get(hero)
        if descriptor is not None:
            reasons.append(Reason(
                code='catalog_hero_features', kind='composition', polarity='neutral', scope='individual', hero_ids=(hero,),
                text='Справочные функции героя не подтверждают его позицию, силу линии или применимость к патчу матча.',
                source_refs=(descriptor.source_ref,), patch_applicability=descriptor.patch_scope,
                evidence={'name': descriptor.name, 'roles': ', '.join(descriptor.roles),
                          'attack_type': descriptor.attack_type},
            ))
    breakdown, composition_reasons = composition(heroes, profiles, complete=complete, patch=patch, config=config)
    if focus is None:
        reasons.extend(composition_reasons)
    else:
        reasons.extend(r.model_copy(update={'scope': 'interaction'}) for r in composition_reasons
                       if r.code == 'conditional_farm_conflict' and focus in r.hero_ids)
    matchup_values: list[float] = []
    threatened: set[int] = set()
    countered: set[int] = set()
    subjects = (focus,) if focus is not None else heroes
    pair_count = len(subjects) * len(enemies)
    for hero in subjects:
        for enemy in enemies:
            value, pair_reasons = matchup(hero, enemy, profiles, patch, statistics, config)
            reasons.extend(pair_reasons)
            if value is not None:
                matchup_values.append(value)
            # Counter labels only from mechanics, never from raw statistical win rates.
            for reason in pair_reasons:
                if reason.kind == 'mechanic' and reason.patch_applicability == f'exact_patch:{patch}':
                    if reason.polarity == 'positive':
                        countered.add(enemy)
                    elif reason.polarity == 'negative':
                        threatened.add(enemy)
    synergy_values: list[float] = []
    seen_synergies: set[tuple[str, tuple[int, int]]] = set()
    for actor in heroes:
        for target in heroes:
            if actor == target or actor not in profiles or target not in profiles:
                continue
            if focus is not None and focus not in (actor, target):
                continue
            for rule in config.rules:
                if rule.kind == 'synergy' and patch in rule.patches and rule.actor_tag in profiles[actor].tags and rule.target_tag in profiles[target].tags:
                    pair: tuple[int, int] = (min(actor, target), max(actor, target)) if rule.directionality == 'symmetric' else (actor, target)
                    key = (rule.code, pair)
                    if key in seen_synergies:
                        continue
                    seen_synergies.add(key)
                    verified = all(patch in value.verified_numeric_patches for value in (profiles[actor], profiles[target])) and patch in rule.verified_numeric_patches
                    if verified:
                        synergy_values.append(rule.utility)
                    reasons.append(Reason(code=rule.code, text=rule.text, kind='mechanic', scope='interaction', polarity='positive',
                        hero_ids=pair, source_refs=tuple(sorted(set(rule.source_refs + profiles[actor].source_refs + profiles[target].source_refs))),
                        confidence='low', patch_applicability=f'exact_patch:{patch}' if verified else 'snapshot_unverified',
                        evidence={'utility': rule.utility} if verified else {}))
    def avg(*names: str) -> float | None:
        values = [breakdown[n] for n in names]
        return mean(v for v in values if v is not None) if all(v is not None for v in values) else None
    if pair_count and len(matchup_values) != pair_count:
        reasons.append(Reason(code='matchup_coverage_incomplete', text='Ось матчапов не рассчитана: подтверждены не все пары с известными соперниками.',
                              kind='limitation', polarity='neutral', scope='data',
                              hero_ids=(focus,) if focus is not None else (),
                              evidence={'supported_pairs': len(matchup_values), 'required_pairs': pair_count}))
    axes: dict[Axis, float | None] = {
        # All currently visible pairs must be supported; unseen opponents are never imputed.
        'matchup': mean(matchup_values) if pair_count and len(matchup_values) == pair_count else None,
        'synergy': mean(synergy_values) if synergy_values else None,
        'balance': avg('initiation_control', 'damage_mix') if focus is None else None,
        'phase': avg('midgame', 'lategame') if focus is None else None,
        'win_condition': avg('objectives', 'lategame') if focus is None else None,
    }
    covered = all(h in profiles for h in heroes)
    if not covered:
        reasons.append(insufficient('hero_or_patch_not_covered'))
    breakdown['synergy'] = axes['synergy']
    breakdown['counters'] = axes['matchup']
    # No populated axis is invented for early picks, unknown heroes or positions.
    evaluation = aggregate(axes, reasons, config, allow_score=covered and bool(heroes))
    return ContextScore(evaluation, breakdown, tuple(sorted(countered)), tuple(sorted(threatened)))
