"""Internal draft contract. Scores are heuristic utilities, never win probabilities."""
from typing import Literal
from pydantic import Field
from app.models.matches import DraftAction, StrictDTO, Team

Confidence = Literal['low', 'medium', 'high']
Axis = Literal['matchup', 'synergy', 'balance', 'phase', 'win_condition']


class Reason(StrictDTO):
    code: str
    text: str
    kind: Literal['mechanic', 'statistic', 'composition', 'limitation']
    polarity: Literal['positive', 'negative', 'neutral']
    scope: Literal['individual', 'interaction', 'team', 'data'] = 'data'
    hero_ids: tuple[int, ...] = ()
    source_refs: tuple[str, ...] = ()
    confidence: Confidence = 'low'
    patch_applicability: str = 'not_verified'
    evidence: dict[str, str | int | float] = Field(default_factory=dict)


class Evaluation(StrictDTO):
    score: float | None = Field(default=None, ge=0, le=100)
    grade: Literal['хороший', 'средний', 'спорный', 'неудачный'] | None = None
    confidence: Confidence = 'low'
    evidence_coverage: float = Field(default=0, ge=0, le=1)
    axes: dict[Axis, float | None] = Field(default_factory=dict)
    reasons: tuple[Reason, ...] = ()


class PickVisibility(StrictDTO):
    own_known_picks_before: tuple[int, ...] = ()
    enemy_revealed_before: tuple[int, ...] = ()
    # Count only: identities of hidden future picks are deliberately not exposed at_pick.
    enemy_hidden_or_unknown: int = Field(default=5, ge=0, le=5)
    bans_known_before: tuple[int, ...] = ()
    stage_index: int | None = None
    sequence_confidence: Confidence = 'low'


class LaterInfluence(StrictDTO):
    hero_id: int
    action_order: int
    score_delta: float | None
    reasons: tuple[Reason, ...]


class PickEvaluation(StrictDTO):
    hero_id: int | None
    hero_name: str | None = None
    team: Team
    action_order: int | None
    source_order: int | None
    stage: int | None
    visibility: PickVisibility
    at_pick: Evaluation
    final_context: Evaluation
    at_pick_score: float | None
    final_score: float | None
    post_pick_delta: float | None
    later_revealed_counters: tuple[LaterInfluence, ...] = ()
    countered_heroes: tuple[int, ...] = ()
    threatened_by_heroes: tuple[int, ...] = ()
    ally_synergies: tuple[Reason, ...] = ()
    resource_warnings: tuple[Reason, ...] = ()
    pros: tuple[str, ...] = ()
    cons: tuple[str, ...] = ()


class TeamDraftScore(StrictDTO):
    team: Team
    evaluation: Evaluation
    breakdown: dict[str, float | None]
    team_win_conditions: tuple[str, ...]
    likely_vulnerabilities: tuple[str, ...]


class DraftReport(StrictDTO):
    match_id: str
    patch: int | None
    mode: Literal['SEQUENTIAL', 'FINAL_ONLY']
    visibility_policy: str
    source_quality: tuple[str, ...]
    # Original actions retained, including bans and rejected orders.
    actions: tuple[DraftAction, ...]
    pick_events: tuple[PickEvaluation, ...]
    teams: dict[Team, TeamDraftScore]
    draft_advantage: Literal['Radiant', 'Dire', 'approximately_even', 'insufficient_data']
    model_version: str
    config_digest: str
    evidence_digest: str
    evidence_coverage: float
    limitations: tuple[str, ...]
