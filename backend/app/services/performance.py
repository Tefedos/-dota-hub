"""Pure role-aware, within-team execution evaluation. No draft/outcome/hero lookup."""
from collections import Counter
from collections.abc import Mapping
import hashlib
import json
from statistics import mean, median
from typing import Literal

from app.models.matches import EvidenceStatus, FarmPositionEvidence, NormalizedMatch, PlayerStat, Team
from app.models.performance import (
    PerformanceSelection, PerformanceSignal, PlayerPerformance, RuinerReport, TeamPerformanceReport,
)
from app.services.performance_config import PerformanceConfig
from app.services.performance_preliminary import select_preliminary
from app.services.match_normalization import kill_participation_counter_ratio

METRICS = ('deaths_per_min', 'kill_participation', 'kda', 'gpm', 'xpm', 'hero_damage_per_min',
           'tower_damage_per_min', 'healing_per_min', 'obs_placed', 'sen_placed', 'observer_kills', 'sentry_kills')
LABELS = {
    'deaths_per_min': 'Смертность в минуту', 'kill_participation': 'Участие в командных убийствах',
    'gpm': 'Золото в минуту', 'xpm': 'Опыт в минуту', 'hero_damage_per_min': 'Урон героям в минуту',
    'tower_damage_per_min': 'Урон строениям в минуту', 'healing_per_min': 'Лечение в минуту',
    'obs_placed': 'Установленные observer wards', 'sen_placed': 'Установленные sentry wards',
    'observer_kills': 'Уничтоженные observer wards', 'sentry_kills': 'Уничтоженные sentry wards',
}


def role_group(position: FarmPositionEvidence) -> Literal['core', 'support', 'unknown']:
    return 'unknown' if position.position is None else 'core' if position.position <= 3 else 'support'


def participation_assessment(player: PlayerStat, match: NormalizedMatch,
                             config: PerformanceConfig) -> tuple[float | None, float | None, str | None]:
    """Return usable ratio, original counter ratio and an exact refusal reason.

    The ratio is not the share of unique kills. An over-100% counter ratio has
    unverified semantics, so it cannot enter the participation comparison yet.
    """
    total = (match.summary.radiant if player.team == Team.RADIANT else match.summary.dire).score
    raw = kill_participation_counter_ratio(player.kills, player.assists, total)
    if player.kills is None:
        return None, raw, 'kill_participation_kills_missing'
    if player.assists is None:
        return None, raw, 'kill_participation_assists_missing'
    if total is None:
        return None, raw, 'kill_participation_team_score_missing'
    if total == 0:
        return None, raw, 'kill_participation_team_score_zero'
    if total < config.minimum_team_kills:
        return None, raw, 'kill_participation_team_score_small'
    involvement = player.kills + player.assists
    deaths = [p.deaths for p in match.players]
    if player.kills > total or (len(deaths) == 10 and all(v is not None for v in deaths)
                                and involvement > sum(v for v in deaths if v is not None)):
        return None, raw, 'kill_participation_counter_anomaly'
    if involvement > total:
        return None, raw, 'kill_participation_over_team_score_unverified'
    return raw, raw, None


def observed(player: PlayerStat, match: NormalizedMatch, config: PerformanceConfig) -> dict[str, float | None]:
    duration = match.summary.duration
    minutes = duration / 60 if duration is not None else None
    def rate(value: int | None) -> float | None:
        return value / minutes if value is not None and minutes else None
    kp, raw_kp, _ = participation_assessment(player, match, config)
    involvement = player.kills + player.assists if player.kills is not None and player.assists is not None else None
    kda = involvement / player.deaths if involvement is not None and player.deaths else None
    return {
        'deaths_per_min': rate(player.deaths), 'kill_participation': kp, 'kda': kda,
        **({'kill_participation_counter_ratio': raw_kp} if raw_kp is not None and kp is None else {}),
        'gpm': float(player.gpm) if player.gpm is not None else None,
        'xpm': float(player.xpm) if player.xpm is not None else None,
        'hero_damage_per_min': rate(player.hero_damage), 'tower_damage_per_min': rate(player.tower_damage),
        'healing_per_min': rate(player.hero_healing),
        **{key: float(value) if (value := getattr(player, key)) is not None else None
           for key in ('obs_placed', 'sen_placed', 'observer_kills', 'sentry_kills')},
    }


def select_team(players: tuple[PlayerPerformance, ...], team: Team, config: PerformanceConfig) -> PerformanceSelection:
    if len(players) != 5 or any(p.error_index is None or p.confidence != 'medium' or p.evidence_coverage < 1 for p in players):
        return PerformanceSelection(evidence=('incomplete_or_low_confidence_team',))
    ranked = sorted(players, key=lambda p: (-(p.error_index or 0), p.player_slot))
    top, second = ranked[:2]
    assert top.error_index is not None and second.error_index is not None
    negative_axes = sum(v is not None and v >= config.signal_threshold for v in top.axes.values())
    if top.error_index < config.selection_threshold:
        return PerformanceSelection(evidence=('below_selection_threshold',))
    if top.error_index - second.error_index < config.selection_margin:
        return PerformanceSelection(evidence=('insufficient_separation',))
    if negative_axes < config.minimum_negative_axes:
        return PerformanceSelection(evidence=('insufficient_independent_signals',))
    return PerformanceSelection(selected_player_slot=top.player_slot, selected_team=team, selection_status='selected',
                                evidence=('relative_signals_not_causality', *tuple(s.code for s in top.negative_signals)))


class RoleAwarePerformanceEvaluator:
    def __init__(self, config: PerformanceConfig | None = None) -> None:
        self.config = config or PerformanceConfig()

    def evaluate(self, match: NormalizedMatch, *, positions: Mapping[int, FarmPositionEvidence] | None = None,
                 selected_team: Team | None = None) -> RuinerReport:
        """positions: trusted internal role evidence, never inferred from lane or hero name."""
        config = self.config
        players = tuple(sorted(match.players, key=lambda p: p.player_slot))
        if len({p.player_slot for p in players}) != len(players) or len(players) > 10:
            raise ValueError('invalid normalized roster')
        if positions and set(positions) - {p.player_slot for p in players}:
            raise ValueError('role evidence references absent player')
        roles = {p.player_slot: (positions or {}).get(p.player_slot, p.performance_position) for p in players}
        conflicts: set[Team] = set()
        for team in Team:
            numbers = [roles[p.player_slot].position for p in players if p.team == team and roles[p.player_slot].position is not None]
            if any(n > 1 for n in Counter(numbers).values()):
                conflicts.add(team)
                for p in players:
                    if p.team == team:
                        roles[p.player_slot] = FarmPositionEvidence()
        observations = {p.player_slot: observed(p, match, config) for p in players}
        supported = match.summary.game_mode in config.supported_modes
        stable_duration = match.summary.duration is not None and match.summary.duration >= config.minimum_duration_seconds
        reports: list[PlayerPerformance] = []
        for player in players:
            role = roles[player.player_slot]
            group = role_group(role)
            same_team = [p for p in players if p.team == player.team]
            cohort = [p for p in same_team if group == 'unknown' or role_group(roles[p.player_slot]) == group]
            peers = [p for p in cohort if p.player_slot != player.player_slot]
            values = observations[player.player_slot]
            positive: list[PerformanceSignal] = []
            negative: list[PerformanceSignal] = []
            reasons: list[str] = []
            limits: list[str] = []
            weights = config.core_weights if group == 'core' else config.fallback_weights
            axes: dict[str, float | None] = dict.fromkeys(weights)
            if role.evidence != EvidenceStatus.CONFIRMED:
                reasons.append('position_unknown' if group == 'unknown' else 'position_estimated')
                limits.append('Позиция 1–5 не подтверждена; уверенность низкая. Линия и имя героя не доказывают роль.')
            if group != 'core':
                reasons.append('economy_not_penalized')
            if player.team in conflicts:
                reasons.append('conflicting_positions')
            if not supported:
                reasons.append('unsupported_game_mode')
            if not stable_duration:
                reasons.append('short_or_unknown_duration')
            team_valid = len(same_team) == 5 and len({p.hero_id for p in same_team}) == 5 and all(p.hero_id is not None and (p.player_slot < 128) == (p.team == Team.RADIANT) for p in same_team)
            if not team_valid:
                reasons.append('incomplete_team')
            _, _, participation_reason = participation_assessment(player, match, config)
            if participation_reason is not None:
                reasons.append(participation_reason)
            if player.deaths == 0:
                reasons.append('kda_zero_denominator')
            if values['kda'] is not None:
                reasons.append('kda_descriptive_only')
            team_deaths = [p.deaths for p in same_team]
            enough_deaths = all(v is not None for v in team_deaths) and sum(v for v in team_deaths if v is not None) >= config.minimum_team_deaths

            def compare(metric: str, *, higher_is_bad: bool = False, credit_only: bool = False) -> float | None:
                value = values[metric]
                available = [(p.player_slot, observations[p.player_slot][metric]) for p in peers
                             if observations[p.player_slot][metric] is not None]
                if value is None or len(available) + 1 < config.minimum_cohort:
                    reasons.append(f'comparison_unavailable:{metric}')
                    return None
                reference = float(median(v for _, v in available if v is not None))
                if reference == 0 and not higher_is_bad:
                    reasons.append(f'zero_comparison_reference:{metric}')
                    if value > 0:
                        positive.append(PerformanceSignal(
                            code=f'observed_contribution:{metric}', metric=metric, value=round(value, 4), reference=0.,
                            comparison_slots=tuple(s for s, _ in available),
                            text=f'{LABELS[metric]}: вклад наблюдается, но ненулевого ориентира для численного сравнения нет.',
                        ))
                    return None
                # A single observed count is the denominator floor, not a claimed performance norm.
                floor = 60 / match.summary.duration if metric.endswith('_per_min') and match.summary.duration else 1.
                if metric == 'kill_participation':
                    total = (match.summary.radiant if player.team == Team.RADIANT else match.summary.dire).score
                    floor = 1 / total if total else 1.
                denom = max(reference, floor)
                bad = min(1., max(0., (value - reference if higher_is_bad else reference - value) / denom))
                good = min(1., max(0., (reference - value if higher_is_bad else value - reference) / denom))
                if not credit_only and bad >= config.signal_threshold:
                    negative.append(PerformanceSignal(
                        code=f'relative_high:{metric}' if higher_is_bad else f'relative_low:{metric}',
                        text=f'{LABELS[metric]}: отклонение от медианы сравниваемых союзников; это сигнал, а не доказательство ошибки.',
                        metric=metric, value=round(value, 4), reference=round(reference, 4),
                        comparison_slots=tuple(s for s, _ in available), magnitude=round(bad, 6),
                    ))
                if good >= config.signal_threshold:
                    positive.append(PerformanceSignal(
                        code=f'positive:{metric}', text=f'{LABELS[metric]}: положительный вклад относительно сравниваемых союзников.',
                        metric=metric, value=round(value, 4), reference=round(reference, 4),
                        comparison_slots=tuple(s for s, _ in available), magnitude=round(good, 6),
                    ))
                return good if credit_only else bad

            if supported and stable_duration and team_valid:
                axes['survival'] = compare('deaths_per_min', higher_is_bad=True) if enough_deaths else None
                axes['participation'] = compare('kill_participation')
                if not enough_deaths:
                    reasons.append('team_deaths_missing_or_small')
                if group == 'core':
                    economy = [compare(metric) for metric in ('gpm', 'xpm')]
                    axes['economy'] = mean(v for v in economy if v is not None) if all(v is not None for v in economy) else None
                    axes['impact'] = compare('hero_damage_per_min')
                # Healing/wards/objectives have no universal required minimum: only observed positive credit.
                credit_metrics: tuple[str, ...] = ('tower_damage_per_min', 'healing_per_min', 'obs_placed', 'sen_placed', 'observer_kills', 'sentry_kills')
                if group != 'core':
                    credit_metrics = ('hero_damage_per_min', *credit_metrics)
                credits = [compare(metric, credit_only=True) for metric in credit_metrics]
                # Maximum rather than sum: multiple correlated ward counters cannot accumulate unbounded credit.
                credit = config.maximum_positive_credit * max((v for v in credits if v is not None), default=0.)
            else:
                credit = 0.
            available_axes = {k: v for k, v in axes.items() if v is not None}
            coverage = sum(weights[k] for k in available_axes)
            enough = len(available_axes) >= config.minimum_axes and coverage + 1e-9 >= config.minimum_coverage
            index = int(max(0., 100 * sum(weights[k] * v for k, v in available_axes.items()) / coverage - credit) + .5) if enough else None
            if index is None:
                reasons.append('insufficient_data')
            confidence: Literal['low', 'medium'] = 'medium' if enough and coverage >= 1 - 1e-9 and role.evidence == EvidenceStatus.CONFIRMED and all(roles[p.player_slot].evidence == EvidenceStatus.CONFIRMED for p in cohort) else 'low'
            limits.append('Сравнение внутри команды и ролевой группы; проверенной популяционной нормы нет. KDA не дублирует штрафы за смерти и участие.')
            reports.append(PlayerPerformance(
                player_slot=player.player_slot, team_player_number=player.team_player_number, hero_id=player.hero_id,
                team=player.team, position=role, role_group=group, error_index=index, confidence=confidence,
                evidence_coverage=round(coverage, 6), axes=axes, observed_metrics=values, positive_credit=round(credit, 4),
                positive_signals=tuple(positive), negative_signals=tuple(negative),
                missing_metrics=tuple(k for k in METRICS if values[k] is None),
                reason_codes=tuple(dict.fromkeys([*reasons, *(s.code for s in positive), *(s.code for s in negative)])),
                limitations=tuple(limits),
            ))
        teams = {}
        for team in Team:
            members = tuple(p for p in reports if p.team == team)
            teams[team] = TeamPerformanceReport(team=team, player_slots=tuple(p.player_slot for p in members),
                scored_players=sum(p.error_index is not None for p in members), selection=select_team(members, team, config),
                threshold=config.selection_threshold, minimum_margin=config.selection_margin,
                preliminary_selection=select_preliminary(members, team))
        summary = teams[selected_team].selection if selected_team is not None else PerformanceSelection(evidence=('team_context_not_provided',))
        scored = sum(p.error_index is not None for p in reports)
        quality: Literal['sufficient', 'partial', 'insufficient'] = 'sufficient' if len(reports) == 10 and all(p.confidence == 'medium' for p in reports) else 'partial' if scored else 'insufficient'
        return RuinerReport(match_id=match.summary.match_id, model_version=config.model_version,
            config_digest=hashlib.sha256(json.dumps(config.model_dump(mode='json'), sort_keys=True).encode()).hexdigest(),
            quality=quality, teams=teams, players=tuple(reports), summary=summary,
            limitations=('Индекс 0–100 отражает относительные признаки проблемного исполнения, не вероятность виновности и не причинность.',
                         'Результат матча и оценки драфта не используются. Radiant и Dire анализируются независимо.',
                         'Веса, пороги и ролевые группы — гипотезы ruiner_v1; малые группы и различия героев ограничивают выводы.'))


def analyze_performance(match: NormalizedMatch, *, config: PerformanceConfig | None = None,
                        positions: Mapping[int, FarmPositionEvidence] | None = None,
                        selected_team: Team | None = None) -> RuinerReport:
    return RoleAwarePerformanceEvaluator(config).evaluate(match, positions=positions, selected_team=selected_team)


def format_performance_summary(report: RuinerReport) -> str:
    lines = ['Индекс исполнения — эвристика, не доказательство чьей-либо вины.']
    for team in Team:
        result = report.teams[team]
        if result.selection.selection_status == 'selected':
            player = next(p for p in report.players if p.player_slot == result.selection.selected_player_slot)
            lines.append(f'{team.value.title()}: наиболее выраженные сигналы у игрока №{player.team_player_number}; индекс {player.error_index}/100.')
        else:
            lines.append(f'{team.value.title()}: индекс рассчитан для {result.scored_players}/{len(result.player_slots)} игроков; оснований выделить одного игрока недостаточно.')
    return '\n'.join(lines)
