"""One manual group request produces independent, versioned public sections."""
import asyncio
import hashlib
import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Protocol, cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Completeness, JsonObject, Match, MatchAnalysis
from app.db.repositories import save_analysis
from app.integrations.opendota import OpenDotaResult, OpenDotaStatus
from app.integrations.opendota_matchups import OpenDotaMatchups
from app.models.match_api import (
    SECTIONS,
    OverviewReport,
    OverviewPlayer,
    OverviewTeam,
    OverviewTeamStats,
    OverviewTeamStatsBySide,
    PlayersReport,
    PublicPlayer,
    Section,
)
from app.models.matches import NormalizedMatch, PlayerStat, QualityStatus, StrictDTO, Team
from app.services.draft.analyzer import analyze_draft, analyze_with_matchups
from app.services.draft.config import default_config
from app.services.match_normalization import normalize_match_snapshot
from app.services.player_catalog import hero_catalog, item_catalog, match_metadata_catalog, resolve_item
from app.services.performance import analyze_performance
from app.services.performance_config import PerformanceConfig
from app.services.timeline import analyze_timeline

logger = logging.getLogger(__name__)
FLOW_VERSION = 'group_flow_v1'
OVERVIEW_MODEL_VERSION = 'overview_v2'
SECTION_VERSIONS = {section: f'{FLOW_VERSION}:{section}' for section in SECTIONS}
ERRORS: dict[str, tuple[int, str, bool]] = {
    'NOT_FOUND': (404, 'Матч не найден в OpenDota', False),
    'RATE_LIMITED': (429, 'OpenDota ограничила частоту запросов. Повторите позже', True),
    'API_UNAVAILABLE': (503, 'OpenDota временно недоступна. Повторите позже', True),
    'MALFORMED_RESPONSE': (502, 'OpenDota вернула некорректные данные матча', True),
    'ANALYSIS_FAILED': (503, 'Часть анализа недоступна. Повторите /match в группе', True),
    'WORKER_RESTARTED': (503, 'Обработка прервана. Повторите /match в группе', True),
}


class Ingestion(Protocol):
    async def ingest_match(self, match_id: int) -> OpenDotaResult: ...


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def public_base(match: NormalizedMatch) -> tuple[OverviewReport, PlayersReport]:
    summary = match.summary
    hero_revision, heroes = hero_catalog()
    item_revision, _ = item_catalog()
    _, modes, patches = match_metadata_catalog()
    overview_players = {
        team: tuple(OverviewPlayer(
            player_slot=player.player_slot, hero_id=player.hero_id,
            hero_name=heroes.get(player.hero_id, {}).get('name') if player.hero_id is not None else None,
            hero_image_url=heroes.get(player.hero_id, {}).get('image_url') if player.hero_id is not None else None,
            display_name=None if player.is_anonymous else player.display_name,
        ) for player in match.players if player.team == team)
        for team in (Team.RADIANT, Team.DIRE)
    }
    overview_limitations = []
    if len(overview_players[Team.RADIANT]) != 5 or len(overview_players[Team.DIRE]) != 5:
        overview_limitations.append('Составы команд неполные; отсутствующие участники не добавлены.')
    if any(player.hero_id is not None and player.hero_name is None for side in overview_players.values() for player in side):
        overview_limitations.append('Имя или портрет неизвестного героя отсутствует в закреплённом каталоге.')
    if summary.game_mode is not None and summary.game_mode not in modes:
        overview_limitations.append('Название игрового режима отсутствует в закреплённом справочнике.')
    if summary.patch is not None and summary.patch not in patches:
        overview_limitations.append('Название патча отсутствует в закреплённом справочнике.')
    if match.source_status == 'FOUND_PARTIAL':
        overview_limitations.append('Исходный ответ OpenDota неполон; полнота базового Обзора оценивается отдельно.')
    overview_limitations.append('Количество разрушенных башен и убийств Roshan не подтверждено полными данными матча.')
    overview = OverviewReport(
        match_id=summary.match_id, duration=summary.duration, start_time=summary.start_time,
        radiant=OverviewTeam(**summary.radiant.model_dump(), players=overview_players[Team.RADIANT]),
        dire=OverviewTeam(**summary.dire.model_dump(), players=overview_players[Team.DIRE]),
        winner=summary.winner, game_mode=summary.game_mode, patch=summary.patch,
        game_mode_name=modes.get(summary.game_mode) if summary.game_mode is not None else None,
        patch_name=patches.get(summary.patch) if summary.patch is not None else None,
        team_stats=OverviewTeamStatsBySide(
            radiant=OverviewTeamStats(kills=summary.radiant.score),
            dire=OverviewTeamStats(kills=summary.dire.score),
        ),
        data_quality=summary.data_quality, source_status=match.source_status,
        limitations=tuple(overview_limitations),
    )
    players = tuple(PublicPlayer(**{
        **{name: getattr(player, name) for name in PublicPlayer.model_fields if name in PlayerStat.model_fields},
        'hero_image_url': heroes.get(player.hero_id, {}).get('image_url') if player.hero_id is not None else None,
        'item_details': tuple(resolve_item(item_id) for item_id in player.items),
        'neutral_item_details': resolve_item(player.neutral_item),
        'backpack_item_details': tuple(resolve_item(item_id) for item_id in player.backpack_items),
    }) for player in match.players)
    limitations = []
    if any(player.is_anonymous for player in players):
        limitations.append('Публичный никнейм отсутствует у части игроков; показана нейтральная подпись.')
    if any(player.hero_id is not None and player.hero_name is None for player in players):
        limitations.append('Часть героев отсутствует в закреплённом каталоге.')
    unknown_lanes = sum(player.position.evidence == 'unknown' for player in players)
    if unknown_lanes == len(players) and players:
        limitations.append('Линии всех игроков не подтверждены данными матча.')
    elif unknown_lanes:
        limitations.append('Линия части игроков не подтверждена данными матча.')
    if any(player.level is None or player.stun_duration_seconds is None or player.buyback_count is None for player in players):
        limitations.append('Часть расширенной статистики недоступна без данных парсинга.')
    if any(item.status == 'unmapped' for player in players for item in (
        *(player.item_details or ()), player.neutral_item_details, *(player.backpack_item_details or ()),
    ) if item is not None):
        limitations.append('Часть предметов не разрешена в закреплённом каталоге.')
    report = PlayersReport(match_id=summary.match_id, players=players,
                           hero_catalog_revision=hero_revision, item_catalog_revision=item_revision,
                           limitations=tuple(limitations))
    return overview, report


async def get_analysis(session: AsyncSession, match_id: int, version: str) -> MatchAnalysis | None:
    return cast(MatchAnalysis | None, await session.scalar(select(MatchAnalysis).where(
        MatchAnalysis.match_id == match_id, MatchAnalysis.algorithm_version == version)))


class MatchAnalysisService:
    """Single polling worker; concurrent chats share work and persisted cache results."""
    def __init__(self, sessions: async_sessionmaker[AsyncSession], ingestion: Ingestion,
                 matchups: OpenDotaMatchups | None = None) -> None:
        self.sessions = sessions
        self.ingestion = ingestion
        self.matchups = matchups
        self._locks: dict[int, asyncio.Lock] = {}
        self._lock_users: dict[int, int] = {}
        self._draft_config = default_config()
        self._hero_names = {hero.hero_id: hero.name for hero in self._draft_config.catalog}
        self._performance_config = PerformanceConfig()
        self.config_version = digest({'flow': FLOW_VERSION, 'overview_model': OVERVIEW_MODEL_VERSION, 'players': 'players_v4', 'draft': self._draft_config.model_dump(mode='json'),
                                      'ruiner': self._performance_config.model_dump(mode='json'), 'timeline': 'timeline_v1'})

    async def _state(self, match_id: int, payload: dict[str, Any]) -> None:
        async with self.sessions() as session, session.begin():
            await session.execute(insert(Match).values(match_id=match_id).on_conflict_do_nothing())
            await save_analysis(session, match_id, FLOW_VERSION,
                                status='pending' if payload['state'] in ('queued', 'running') else payload['state'],
                                report_payload=cast(JsonObject, payload), computed_at=datetime.now(UTC))

    async def recover_interrupted(self) -> int:
        """Called once under the polling-worker singleton lock, never by web startup."""
        count = 0
        async with self.sessions() as session, session.begin():
            rows = (await session.scalars(select(MatchAnalysis).where(
                MatchAnalysis.algorithm_version == FLOW_VERSION, MatchAnalysis.status == 'pending'))).all()
            for row in rows:
                row.status = 'failed'
                row.computed_at = datetime.now(UTC)
                row.report_payload = {'state': 'failed', 'available_sections': [], 'error_code': 'WORKER_RESTARTED'}
                count += 1
        return count

    async def process(self, match_id: int) -> str:
        lock = self._locks.setdefault(match_id, asyncio.Lock())
        self._lock_users[match_id] = self._lock_users.get(match_id, 0) + 1
        try:
            async with lock:
                return await self._process(match_id)
        finally:
            self._lock_users[match_id] -= 1
            if self._lock_users[match_id] == 0:
                self._locks.pop(match_id, None)
                self._lock_users.pop(match_id, None)

    async def _process(self, match_id: int) -> str:
        async with self.sessions() as session:
            previous_row = await get_analysis(session, match_id, FLOW_VERSION)
            previous = dict(previous_row.report_payload or {}) if previous_row else {}
        await self._state(match_id, {'state': 'queued', 'available_sections': []})
        try:
            await self._state(match_id, {'state': 'running', 'available_sections': []})
            result = await self.ingestion.ingest_match(match_id)
            if result.status not in {OpenDotaStatus.FOUND_FULL, OpenDotaStatus.FOUND_PARTIAL} or result.snapshot is None:
                code = result.status.value if result.status.value in ERRORS else 'MALFORMED_RESPONSE'
                await self._state(match_id, {'state': 'failed', 'available_sections': [], 'error_code': code,
                                            'retry_after_seconds': result.retry_after_seconds})
                return ERRORS[code][1]
            if result.match_id != match_id or result.snapshot.get('match', {}).get('match_id') != match_id:
                raise ValueError('match identity mismatch')
            source_digest = digest({key: result.snapshot.get(key) for key in ('match', 'status', 'schema_version')})
            if previous.get('state') == 'ready' and previous.get('source_digest') == source_digest and previous.get('config_version') == self.config_version:
                await self._state(match_id, previous)
                return str(previous['summary']) + '\nИз сохранённого анализа.'
            try:
                normalized = normalize_match_snapshot(result.snapshot, hero_names=self._hero_names)
            except (ValueError, TypeError, KeyError):
                await self._state(match_id, {'state': 'failed', 'available_sections': [], 'error_code': 'MALFORMED_RESPONSE'})
                return ERRORS['MALFORMED_RESPONSE'][1]
            reports: dict[Section, StrictDTO] = {}
            overview, players = public_base(normalized)
            reports['overview'], reports['players'] = overview, players
            failed: list[str] = []
            try:
                reports['draft'] = (await analyze_with_matchups(normalized, self.matchups, config=self._draft_config)
                                    if self.matchups is not None else analyze_draft(normalized, config=self._draft_config))
            except Exception as error:  # noqa: BLE001 - isolate external failures without leaking exception text
                logger.error('Analysis section failed match_id=%s section=draft error_type=%s', match_id, type(error).__name__)
                failed.append('draft')
            evaluators: dict[Section, Callable[[], StrictDTO]] = {
                'ruiner': lambda: analyze_performance(normalized, config=self._performance_config),
                'timeline': lambda: analyze_timeline(normalized),
            }
            for section, evaluate in evaluators.items():
                try:
                    reports[section] = evaluate()
                except Exception as error:  # noqa: BLE001 - isolate external failures without leaking exception text
                    logger.error('Analysis section failed match_id=%s section=%s error_type=%s', match_id, section, type(error).__name__)
                    failed.append(section)
            timeline_report = reports.get('timeline')
            timeline_quality = timeline_report.model_dump(mode='json')['quality'] if timeline_report else 'unavailable'
            reports['overview'] = overview.model_copy(update={'data_quality': overview.data_quality.model_copy(
                update={'timeline': QualityStatus(timeline_quality)},
            ), 'limitations': overview.limitations + (
                ('Хронология матча недоступна без данных парсинга; базовый обзор доступен.',)
                if timeline_quality == 'unavailable' else
                ('Хронология матча неполна; базовый обзор доступен.',)
                if timeline_quality == 'partial' else ()
            )})
            summary = format_group_summary(match_id, reports)
            now = datetime.now(UTC)
            state = {'state': 'failed' if failed else 'ready', 'source_digest': source_digest,
                     'config_version': self.config_version, 'available_sections': list(reports),
                     'error_code': 'ANALYSIS_FAILED' if failed else None, 'failed_sections': failed, 'summary': summary}
            async with self.sessions() as session, session.begin():
                for section, report in reports.items():
                    data = report.model_dump(mode='json')
                    complete: Completeness = 'partial'
                    if section == 'overview' and normalized.summary.data_quality.summary.value == 'complete' or section == 'players' and normalized.summary.data_quality.stats.value == 'complete':
                        complete = 'full'
                    elif section == 'timeline':
                        complete = {'complete': 'full', 'partial': 'partial', 'unavailable': 'missing'}[data['quality']]  # type: ignore[assignment]
                    elif section == 'ruiner':
                        complete = {'sufficient': 'full', 'partial': 'partial', 'insufficient': 'missing'}[data['quality']]  # type: ignore[assignment]
                    limitations = list(data.get('limitations', []))
                    if section in ('overview', 'players') and complete != 'full':
                        limitations.append('Часть базовой статистики отсутствует; неизвестные значения оставлены null.')
                    await save_analysis(session, match_id, SECTION_VERSIONS[section], status='ready', completeness=complete,
                        computed_at=now, report_payload=cast(JsonObject, {
                            'schema_version': 1, 'source_digest': source_digest, 'data': data,
                            'model_version': data.get('model_version', OVERVIEW_MODEL_VERSION if section == 'overview' else f'{section}_v1'),
                            'config_version': data.get('config_digest', self.config_version),
                            'limitations': limitations,
                        }))
                await save_analysis(session, match_id, FLOW_VERSION, status='failed' if failed else 'ready',
                                    report_payload=cast(JsonObject, state), computed_at=now)
            return summary
        except asyncio.CancelledError:
            await self._state(match_id, {'state': 'failed', 'available_sections': [], 'error_code': 'WORKER_RESTARTED'})
            raise
        except Exception as error:  # noqa: BLE001 - isolate external failures without leaking exception text
            logger.error('Group analysis failed match_id=%s error_type=%s', match_id, type(error).__name__)
            await self._state(match_id, {'state': 'failed', 'available_sections': [], 'error_code': 'ANALYSIS_FAILED'})
            return ERRORS['ANALYSIS_FAILED'][1]


def format_group_summary(match_id: int, reports: dict[Section, StrictDTO]) -> str:
    """Fixed short text, no player names or provider-controlled strings; parse_mode=None."""
    overview = reports['overview'].model_dump(mode='json')
    duration = overview['duration']
    clock = f'{duration // 60}:{duration % 60:02d}' if duration is not None else 'нет данных'
    radiant, dire = overview['radiant']['score'], overview['dire']['score']
    score = f'{radiant}:{dire}' if radiant is not None and dire is not None else 'нет данных'
    winner = {'radiant': 'Radiant', 'dire': 'Dire'}.get(overview['winner'], 'нет данных')
    lines = [f'Матч {match_id} · {clock}', f'Radiant / Dire · счёт {score}', f'Победитель: {winner}']
    draft = reports.get('draft')
    data = draft.model_dump(mode='json') if draft else {}
    for team in ('radiant', 'dire'):
        value = data.get('teams', {}).get(team, {}).get('evaluation', {}).get('score')
        lines.append(f'Драфт {team.title()}: {value if value is not None else "нет данных"}')
    performance = reports.get('ruiner')
    eligible = [p for p in performance.model_dump(mode='json')['players'] if p['confidence'] != 'low' and p['error_index'] is not None] if performance else []
    if eligible:
        lines.append('Индекс ошибок (эвристика): ' + '; '.join(f'{p["team"].title()} #{p["team_player_number"]}: {p["error_index"]}' for p in eligible))
    else:
        lines.append('Индекс ошибок: недостаточно уверенных данных')
    timeline = reports.get('timeline')
    if timeline:
        td = timeline.model_dump(mode='json')
        lines.append(f'Событий: {len(td["events"])} · полнота: {td["quality"]}')
    else:
        lines.append('Хронология: нет данных')
    lines.append('Доступность и ограничения разделов — в подробном анализе.')
    return '\n'.join(lines)[:3500]
