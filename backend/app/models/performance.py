"""Execution signals are relative heuristics, never a probability of blame."""
from typing import Literal
from pydantic import Field, model_validator
from app.models.matches import FarmPositionEvidence, StrictDTO, Team


class PerformanceSignal(StrictDTO):
    code: str
    text: str
    metric: str
    value: float
    reference: float | None = None
    comparison_slots: tuple[int, ...] = ()
    magnitude: float = Field(default=0, ge=0, le=1)
    source_ref: str = 'normalized_match'


class PlayerPerformance(StrictDTO):
    player_slot: int
    team_player_number: int
    hero_id: int | None
    team: Team
    position: FarmPositionEvidence
    role_group: Literal['core', 'support', 'unknown']
    error_index: int | None = Field(default=None, ge=0, le=100)
    confidence: Literal['low', 'medium'] = 'low'
    evidence_coverage: float = Field(default=0, ge=0, le=1)
    axes: dict[str, float | None]
    observed_metrics: dict[str, float | None]
    positive_credit: float = Field(default=0, ge=0)
    positive_signals: tuple[PerformanceSignal, ...] = ()
    negative_signals: tuple[PerformanceSignal, ...] = ()
    missing_metrics: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class PerformanceSelection(StrictDTO):
    selected_player_slot: int | None = None
    selected_team: Team | None = None
    selection_status: Literal['selected', 'no_confident_selection'] = 'no_confident_selection'
    evidence: tuple[str, ...] = ()


PreliminaryReason = Literal[
    'highest_relative_index', 'close_scores', 'incomplete_team', 'invalid_roster',
    'incomplete_player_scores', 'invalid_player_scores', 'all_indices_zero',
    'leader_signals_missing', 'confirmed_leaver', 'invalid_leaver_context',
    'blocking_player_context', 'roles_unknown', 'roles_unconfirmed', 'leaver_context_unknown',
    'stored_projection_inconsistent',
]


class PreliminarySelection(StrictDTO):
    projection_version: Literal['ri_preliminary_v1'] = 'ri_preliminary_v1'
    minimum_margin: Literal[15] = 15
    status: Literal['single', 'group', 'none'] = 'none'
    player_slots: tuple[int, ...] = ()
    leader_slot: int | None = None
    highest_index: int | None = Field(default=None, ge=1, le=100)
    margin: int | None = Field(default=None, ge=0, le=100)
    confidence: Literal['low', 'medium'] = 'low'
    reason_codes: tuple[PreliminaryReason, ...]

    @model_validator(mode='after')
    def coherent_result(self) -> 'PreliminarySelection':
        slots = self.player_slots
        if len(set(slots)) != len(slots) or any(s not in (*range(5), *range(128, 133)) for s in slots):
            raise ValueError('invalid preliminary slots')
        if slots and not (all(s < 128 for s in slots) or all(s >= 128 for s in slots)):
            raise ValueError('preliminary comparison must stay within one team')
        if not self.reason_codes:
            raise ValueError('preliminary reason required')
        if self.status == 'none':
            if slots or self.leader_slot is not None or self.highest_index is not None or self.margin is not None:
                raise ValueError('none must not claim a comparison')
        elif self.highest_index is None or self.margin is None or self.margin > self.highest_index:
            raise ValueError('comparison values required')
        elif self.status == 'single':
            if len(slots) != 1 or self.leader_slot != slots[0] or self.margin < self.minimum_margin:
                raise ValueError('single requires separation')
        elif not 2 <= len(slots) <= 5 or self.leader_slot is not None or self.margin >= self.minimum_margin:
            raise ValueError('group requires close scores')
        return self


class TeamPerformanceReport(StrictDTO):
    team: Team
    player_slots: tuple[int, ...]
    scored_players: int
    selection: PerformanceSelection
    threshold: int
    minimum_margin: int
    # Legacy persisted reports remain readable; the API projects missing results at read time.
    preliminary_selection: PreliminarySelection | None = None


class RuinerReport(StrictDTO):
    match_id: str
    model_version: str
    config_digest: str
    quality: Literal['sufficient', 'partial', 'insufficient']
    teams: dict[Team, TeamPerformanceReport]
    players: tuple[PlayerPerformance, ...]
    summary: PerformanceSelection
    limitations: tuple[str, ...]
