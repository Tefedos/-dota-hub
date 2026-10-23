from typing import Literal

from pydantic import Field, JsonValue

from app.models.matches import QualityStatus, StrictDTO, Team


class TimelineActor(StrictDTO):
    player_slot: int = Field(ge=0, le=255)
    team: Team
    hero_id: int | None = None
    hero_name: str | None = None


class TimelineEvent(StrictDTO):
    id: str
    time_seconds: int | None
    time_start: int
    time_end: int
    time_precision: Literal["exact", "interval"]
    display_clock: str
    type: str
    team: Team | None
    side: Team | None
    actors: tuple[TimelineActor, ...]
    description: str
    evidence: dict[str, JsonValue]
    evidence_quality: Literal["confirmed", "partial"]
    source_field: str
    original_ref: str
    original_refs: tuple[str, ...]
    dedupe_key: str
    reason_codes: tuple[str, ...]
    related_event_ids: tuple[str, ...] = ()


class AdvantagePoint(StrictDTO):
    time_seconds: int
    value: int | float
    advantage_for: Team | None
    source_field: str


class TurningPoint(StrictDTO):
    time_start: int
    time_end: int
    delta: int | float
    gold_delta: int | float | None
    xp_delta: int | float | None
    direction: Team
    reason_codes: tuple[str, ...]
    confidence: Literal["low", "medium"]
    related_event_ids: tuple[str, ...]
    evidence: dict[str, JsonValue]


class TimelineReport(StrictDTO):
    match_id: str
    quality: QualityStatus
    timeline_data_status: QualityStatus
    available_types: tuple[str, ...]
    supported_event_types: tuple[str, ...]
    missing_event_types: tuple[str, ...]
    event_coverage: float = Field(ge=0, le=1)
    empty_state_text: str | None
    events: tuple[TimelineEvent, ...]
    gold_adv_points: tuple[AdvantagePoint, ...]
    xp_adv_points: tuple[AdvantagePoint, ...]
    turning_points: tuple[TurningPoint, ...]
    limitations: tuple[str, ...]
