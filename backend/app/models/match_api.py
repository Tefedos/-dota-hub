"""Public match contracts: no raw snapshots or player account identifiers."""
from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import Field

from app.models.matches import (
    DataQuality,
    FarmPositionEvidence,
    PositionEvidence,
    StrictDTO,
    Team,
    TeamSummary,
)

Section = Literal['overview', 'players', 'draft', 'ruiner', 'timeline']
FlowStatus = Literal['queued', 'running', 'ready', 'failed']
SECTIONS: tuple[Section, ...] = ('overview', 'players', 'draft', 'ruiner', 'timeline')


class MatchError(StrictDTO):
    code: str
    message: str
    retryable: bool


class AnalysisState(StrictDTO):
    status: FlowStatus
    available_sections: tuple[Section, ...] = ()
    error_code: str | None = None


class OverviewPlayer(StrictDTO):
    player_slot: int
    hero_id: int | None = None
    hero_name: str | None = None
    hero_image_url: str | None = None
    display_name: str | None = None


class OverviewTeam(TeamSummary):
    players: tuple[OverviewPlayer, ...] = ()


class OverviewTeamStats(StrictDTO):
    kills: int | None = None
    towers_destroyed: int | None = None
    roshan_kills: int | None = None


class OverviewTeamStatsBySide(StrictDTO):
    radiant: OverviewTeamStats
    dire: OverviewTeamStats


class OverviewReport(StrictDTO):
    match_id: str
    duration: int | None
    radiant: OverviewTeam
    dire: OverviewTeam
    winner: Team | None
    start_time: int | None
    game_mode: int | None
    patch: int | None
    game_mode_name: str | None = None
    patch_name: str | None = None
    team_stats: OverviewTeamStatsBySide | None = None
    data_quality: DataQuality
    source_status: str | None
    limitations: tuple[str, ...] = ()


class PublicItem(StrictDTO):
    item_id: int = Field(ge=0)
    name: str | None = None
    image_key: str | None = None
    image_url: str | None = None
    status: Literal['empty', 'known', 'unmapped']


class PublicPlayer(StrictDTO):
    player_slot: int
    team: Team
    team_player_number: int
    display_name: str
    hero_id: int | None
    hero_name: str | None
    kills: int | None
    deaths: int | None
    assists: int | None
    last_hits: int | None
    denies: int | None
    gpm: int | None
    xpm: int | None
    hero_damage: int | None
    tower_damage: int | None
    hero_healing: int | None
    net_worth: int | None
    obs_placed: int | None = None
    sen_placed: int | None = None
    items: tuple[int | None, ...]
    neutral_item: int | None
    position: PositionEvidence
    name_source: Literal['opendota'] | None = None
    is_anonymous: bool | None = None
    hero_image_url: str | None = None
    item_details: tuple[PublicItem | None, ...] | None = None
    neutral_item_details: PublicItem | None = None
    backpack_items: tuple[int | None, ...] | None = None
    backpack_item_details: tuple[PublicItem | None, ...] | None = None
    level: int | None = Field(default=None, ge=1)
    stun_duration_seconds: float | None = Field(default=None, ge=0)
    buyback_count: int | None = Field(default=None, ge=0)
    performance_position: FarmPositionEvidence = Field(default_factory=FarmPositionEvidence)


class PlayersReport(StrictDTO):
    match_id: str
    players: tuple[PublicPlayer, ...]
    completeness_scope: Literal['core_player_stats'] = 'core_player_stats'
    hero_catalog_revision: str | None = None
    item_catalog_revision: str | None = None
    limitations: tuple[str, ...] = ()


T = TypeVar('T')


class MatchEnvelope(StrictDTO, Generic[T]):
    schema_version: Literal[1] = 1
    match_id: str | None = None
    status: FlowStatus
    available_sections: tuple[Section, ...] = ()
    data: T | None = None
    error: MatchError | None = None
    limitations: tuple[str, ...] = ()
    model_version: str | None = None
    config_version: str | None = None
    analyzed_at: datetime | None = None
    completeness: Literal['full', 'partial', 'missing'] | None = None
    retry_after_seconds: int | None = Field(default=None, ge=1)
