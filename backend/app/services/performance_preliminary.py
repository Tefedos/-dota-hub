"""RI-04 projection over existing indices; never changes ruiner_v1 scoring or strict selection."""
from collections.abc import Mapping
from typing import Literal

from app.models.matches import EvidenceStatus, Team
from app.models.performance import PlayerPerformance, PreliminaryReason, PreliminarySelection, RuinerReport

PRELIMINARY_MARGIN = 15
BLOCKING_REASONS = frozenset({
    'unsupported_game_mode', 'short_or_unknown_duration', 'incomplete_team',
    'conflicting_positions', 'insufficient_data',
})


def select_preliminary(
    players: tuple[PlayerPerformance, ...], team: Team, *,
    leaver_context: Mapping[int, bool | None] | None = None,
) -> PreliminarySelection:
    """Accept only this team's players and trusted explicit leaver evidence.

    True means a confirmed leaver, False means confirmed non-leaver, None/missing
    means unknown. Current ingestion supplies no such evidence. This internal hook
    is deliberately not inferred from disconnects, missing stats, hero or outcome.
    """
    confidence: Literal['low', 'medium'] = 'medium' if players and all(p.confidence == 'medium' for p in players) else 'low'
    limitations: list[PreliminaryReason] = []
    if any(p.position.position is None for p in players):
        limitations.append('roles_unknown')
    elif any(p.position.evidence != EvidenceStatus.CONFIRMED for p in players):
        limitations.append('roles_unconfirmed')
    context = leaver_context or {}
    if any(context.get(p.player_slot) is None for p in players) or not players:
        limitations.append('leaver_context_unknown')

    def refuse(reason: PreliminaryReason) -> PreliminarySelection:
        return PreliminarySelection(confidence=confidence, reason_codes=(reason, *limitations))

    if len(players) != 5:
        return refuse('incomplete_team')
    expected = set(range(5)) if team == Team.RADIANT else set(range(128, 133))
    if (any(p.team != team or type(p.hero_id) is not int or p.hero_id <= 0 for p in players)
        or {p.player_slot for p in players} != expected or len({p.hero_id for p in players}) != 5):
        return refuse('invalid_roster')
    if set(context) - expected or any(value is not None and type(value) is not bool for value in context.values()):
        return refuse('invalid_leaver_context')
    if any(value is True for value in context.values()):
        return refuse('confirmed_leaver')
    if any(p.error_index is None for p in players):
        return refuse('incomplete_player_scores')
    if any(type(p.error_index) is not int or not 0 <= p.error_index <= 100 for p in players):
        return refuse('invalid_player_scores')
    if any(BLOCKING_REASONS.intersection(p.reason_codes) for p in players):
        return refuse('blocking_player_context')
    def rank_key(player: PlayerPerformance) -> tuple[int, int]:
        assert player.error_index is not None  # All five scores were checked above; never null -> zero.
        return (-player.error_index, player.player_slot)
    ranked = sorted(players, key=rank_key)
    highest, second = ranked[0].error_index, ranked[1].error_index
    assert highest is not None and second is not None
    if highest == 0:
        return refuse('all_indices_zero')
    if any(not p.negative_signals for p in ranked if p.error_index == highest):
        return refuse('leader_signals_missing')
    margin = highest - second
    single = margin >= PRELIMINARY_MARGIN
    slots = (ranked[0].player_slot,) if single else tuple(
        p.player_slot for p in ranked if p.error_index is not None and p.error_index > 0
        and highest - p.error_index < PRELIMINARY_MARGIN
    )
    return PreliminarySelection(
        status='single' if single else 'group', player_slots=slots,
        leader_slot=slots[0] if single else None, highest_index=highest, margin=margin,
        confidence=confidence,
        reason_codes=('highest_relative_index' if single else 'close_scores', *limitations),
    )


def project_preliminary(report: RuinerReport) -> RuinerReport:
    """Validate stored projections against player evidence without changing persisted JSON."""
    teams = {}
    for side, row in report.teams.items():
        players = tuple(p for p in report.players if p.team == side)
        expected = select_preliminary(players, side)
        roster_agrees = (row.team == side and row.player_slots == tuple(p.player_slot for p in players)
                         and row.scored_players == sum(p.error_index is not None for p in players))
        stored = row.preliminary_selection
        if stored is None and roster_agrees:
            projection = expected  # Legacy report: no earlier preliminary decision to distrust.
        elif stored is not None and roster_agrees and stored == expected:
            projection = stored
        elif stored is not None and roster_agrees and stored.status == 'none' and stored.reason_codes[:1] == ('confirmed_leaver',) and any(
            stored == select_preliminary(players, side, leaver_context=context)
            for p in players for context in (
                {p.player_slot: True},
                {member.player_slot: member.player_slot == p.player_slot for member in players},
            )
        ):
            # Preserve a conservative saved refusal. The leaver evidence itself is not recovered here.
            projection = stored
        else:
            # A contradicted saved choice may have depended on leaver evidence that is no longer stored.
            # Never reconstruct a leader from the same indices alone.
            limitations = tuple(code for code in expected.reason_codes
                                if code in {'roles_unknown', 'roles_unconfirmed', 'leaver_context_unknown'})
            projection = PreliminarySelection(confidence=expected.confidence,
                reason_codes=('stored_projection_inconsistent', *limitations,
                    *(() if 'leaver_context_unknown' in limitations else ('leaver_context_unknown',))))
        teams[side] = row if stored == projection else row.model_copy(update={'preliminary_selection': projection})
    return report.model_copy(update={'teams': teams})
