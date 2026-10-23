from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator


class StrictDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Team(StrEnum):
    RADIANT = "radiant"
    DIRE = "dire"


class QualityStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class EvidenceStatus(StrEnum):
    CONFIRMED = "confirmed"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class Position(StrEnum):
    SAFE_LANE = "safe_lane"
    MID_LANE = "mid_lane"
    OFF_LANE = "off_lane"
    JUNGLE = "jungle"
    UNKNOWN = "unknown"


class MetricStatus(StrEnum):
    AVAILABLE = "available"
    INPUTS_MISSING = "inputs_missing"
    DENOMINATOR_ZERO = "denominator_zero"


class PlayerField(StrEnum):
    HERO_ID = "hero_id"
    ACCOUNT_ID = "account_id"
    STEAM_ID = "steam_id"
    KILLS = "kills"
    DEATHS = "deaths"
    ASSISTS = "assists"
    LAST_HITS = "last_hits"
    DENIES = "denies"
    GPM = "gpm"
    XPM = "xpm"
    HERO_DAMAGE = "hero_damage"
    TOWER_DAMAGE = "tower_damage"
    HERO_HEALING = "hero_healing"
    NET_WORTH = "net_worth"
    ITEMS = "items"
    NEUTRAL_ITEM = "neutral_item"
    ITEM_TIMINGS = "item_timings"
    POSITION = "position"
    PERFORMANCE_POSITION = "performance_position"
    OBS_PLACED = "obs_placed"
    SEN_PLACED = "sen_placed"
    OBSERVER_KILLS = "observer_kills"
    SENTRY_KILLS = "sentry_kills"
    LEVEL = "level"
    STUN_DURATION_SECONDS = "stun_duration_seconds"
    BUYBACK_COUNT = "buyback_count"
    BACKPACK_ITEMS = "backpack_items"


class SummaryField(StrEnum):
    RADIANT_SCORE = "radiant_score"
    DIRE_SCORE = "dire_score"
    WINNER = "winner"
    DURATION = "duration"
    START_TIME = "start_time"
    GAME_MODE = "game_mode"
    LOBBY_TYPE = "lobby_type"
    PATCH = "patch"
    RADIANT_TEAM_ID = "radiant_team_id"
    DIRE_TEAM_ID = "dire_team_id"
    RADIANT_NAME = "radiant_name"
    DIRE_NAME = "dire_name"


class DataQuality(StrictDTO):
    summary: QualityStatus
    stats: QualityStatus
    draft_order: QualityStatus
    timeline: QualityStatus
    roles: QualityStatus


class PositionEvidence(StrictDTO):
    position: Position
    evidence: EvidenceStatus
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_field: str | None = None

    @model_validator(mode="after")
    def validate_evidence(self) -> "PositionEvidence":
        if self.evidence == EvidenceStatus.UNKNOWN:
            if self.position != Position.UNKNOWN or self.confidence is not None or self.source_field is not None:
                raise ValueError("unknown position evidence cannot claim a position or confidence")
        elif self.position == Position.UNKNOWN or self.confidence is None or self.source_field is None:
            raise ValueError("confirmed or estimated positions require evidence details")
        return self


class FarmPositionEvidence(StrictDTO):
    position: int | None = Field(default=None, ge=1, le=5)
    evidence: EvidenceStatus = EvidenceStatus.UNKNOWN
    source_field: str | None = None

    @model_validator(mode="after")
    def consistent(self) -> "FarmPositionEvidence":
        if self.evidence == EvidenceStatus.UNKNOWN:
            if self.position is not None or self.source_field is not None:
                raise ValueError("unknown farm position cannot claim evidence")
        elif self.position is None or not self.source_field:
            raise ValueError("known farm position requires provenance")
        return self


class PlayerStat(StrictDTO):
    team: Team
    player_slot: int = Field(ge=0, le=255)
    team_player_number: int = Field(ge=1, le=5)
    display_name: str
    name_source: Literal["opendota"] | None = None
    is_anonymous: bool = True
    hero_id: int | None = Field(default=None, gt=0)
    hero_name: str | None = None
    account_id: str | None = None
    steam_id: str | None = None
    kills: int | None = Field(default=None, ge=0)
    deaths: int | None = Field(default=None, ge=0)
    assists: int | None = Field(default=None, ge=0)
    last_hits: int | None = Field(default=None, ge=0)
    denies: int | None = Field(default=None, ge=0)
    gpm: int | None = Field(default=None, ge=0)
    xpm: int | None = Field(default=None, ge=0)
    hero_damage: int | None = Field(default=None, ge=0)
    tower_damage: int | None = Field(default=None, ge=0)
    hero_healing: int | None = Field(default=None, ge=0)
    net_worth: int | None = Field(default=None, ge=0)
    level: int | None = Field(default=None, ge=1)
    stun_duration_seconds: float | None = Field(default=None, ge=0)
    buyback_count: int | None = Field(default=None, ge=0)
    obs_placed: int | None = Field(default=None, ge=0)
    sen_placed: int | None = Field(default=None, ge=0)
    observer_kills: int | None = Field(default=None, ge=0)
    sentry_kills: int | None = Field(default=None, ge=0)
    performance_position: FarmPositionEvidence = Field(default_factory=FarmPositionEvidence)
    items: tuple[int | None, ...] = Field(min_length=6, max_length=6)
    backpack_items: tuple[int | None, ...] = (None, None, None)
    neutral_item: int | None = Field(default=None, ge=0)
    item_timings: dict[str, tuple[int, ...]] | None = None
    position: PositionEvidence
    available_fields: tuple[PlayerField, ...]


class HeroRosterEntry(StrictDTO):
    team: Team
    player_slot: int = Field(ge=0, le=255)
    hero_id: int | None = Field(default=None, gt=0)
    hero_name: str | None = None


class TeamSummary(StrictDTO):
    team: Team
    team_id: str | None = None
    name: str | None = None
    score: int | None = Field(default=None, ge=0)


class MatchSummary(StrictDTO):
    match_id: str
    radiant: TeamSummary
    dire: TeamSummary
    winner: Team | None
    duration: int | None = Field(default=None, gt=0)
    start_time: int | None = Field(default=None, ge=0)
    game_mode: int | None = Field(default=None, ge=0)
    lobby_type: int | None = Field(default=None, ge=0)
    patch: int | None = Field(default=None, ge=0)
    hero_roster: tuple[HeroRosterEntry, ...]
    available_fields: tuple[SummaryField, ...]
    data_quality: DataQuality
    source_version: int = Field(ge=1)


class DraftAction(StrictDTO):
    source_order: int = Field(ge=0)
    is_pick: bool | None
    hero_id: int | None = Field(default=None, gt=0)
    team_code: int | None
    team: Team | None
    order: int | None = Field(default=None, ge=0)


class DraftRawData(StrictDTO):
    available: bool
    actions: tuple[DraftAction, ...]
    duplicate_orders: tuple[int, ...]
    duplicate_actions_source_orders: tuple[int, ...]
    missing_orders: tuple[int, ...]
    invalid_source_orders: tuple[int, ...]
    completeness: QualityStatus


class PlayerEventLogs(StrictDTO):
    player_slot: int = Field(ge=0, le=255)
    kills_log: tuple[JsonValue, ...] | None = None
    buyback_log: tuple[JsonValue, ...] | None = None
    purchase_log: tuple[JsonValue, ...] | None = None


class MatchEventRawData(StrictDTO):
    objectives: tuple[JsonValue, ...] | None
    kills_log: tuple[JsonValue, ...] | None
    teamfights: tuple[JsonValue, ...] | None
    radiant_gold_adv: tuple[int | float | None, ...] | None
    radiant_xp_adv: tuple[int | float | None, ...] | None
    completeness: QualityStatus
    buyback_log: tuple[JsonValue, ...] | None = None
    purchase_log: tuple[JsonValue, ...] | None = None
    player_logs: tuple[PlayerEventLogs, ...] = ()


class NormalizedRawData(StrictDTO):
    draft: DraftRawData
    events: MatchEventRawData


class DerivedMetric(StrictDTO):
    value: float | None
    status: MetricStatus
    decimal_places: int | None = Field(default=None, ge=0, le=8)

    @model_validator(mode="after")
    def validate_metric(self) -> "DerivedMetric":
        if self.status == MetricStatus.AVAILABLE:
            if self.value is None or self.decimal_places is None:
                raise ValueError("available metrics require a value and declared precision")
        elif self.value is not None or self.decimal_places is not None:
            raise ValueError("unavailable metrics cannot contain a value or precision")
        return self


class PlayerDerivedStats(StrictDTO):
    player_slot: int = Field(ge=0, le=255)
    kda: DerivedMetric
    kill_participation: DerivedMetric


class NormalizedMatch(StrictDTO):
    normalized_version: int = 1
    source: str
    source_fetched_at: datetime
    summary: MatchSummary
    players: tuple[PlayerStat, ...]
    raw: NormalizedRawData
    derived: tuple[PlayerDerivedStats, ...]
    source_status: str | None = None
