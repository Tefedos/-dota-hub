"""Execution signals are relative heuristics, never a probability of blame."""
from typing import Literal
from pydantic import Field
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


class TeamPerformanceReport(StrictDTO):
    team: Team
    player_slots: tuple[int, ...]
    scored_players: int
    selection: PerformanceSelection
    threshold: int
    minimum_margin: int


class RuinerReport(StrictDTO):
    match_id: str
    model_version: str
    config_digest: str
    quality: Literal['sufficient', 'partial', 'insufficient']
    teams: dict[Team, TeamPerformanceReport]
    players: tuple[PlayerPerformance, ...]
    summary: PerformanceSelection
    limitations: tuple[str, ...]
