"""Optional acquisition. The analyzer consumes a frozen batch and never fetches implicitly."""
import asyncio
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, ValidationError, model_validator
from app.models.matches import StrictDTO
from app.integrations.opendota import OpenDotaClient


class MatchupStat(StrictDTO):
    hero_id: int = Field(gt=0)
    opponent_id: int = Field(gt=0)
    games_played: int = Field(ge=0)
    wins: int = Field(ge=0)
    source_ref: str
    fetched_at: datetime
    # Endpoint has no guaranteed patch, position, bracket or time filter.
    patch_scope: Literal['aggregate_unknown'] = 'aggregate_unknown'

    @model_validator(mode='after')
    def check_counts(self) -> 'MatchupStat':
        if self.wins > self.games_played or self.hero_id == self.opponent_id:
            raise ValueError('invalid matchup counts or identity')
        if self.fetched_at.utcoffset() is None:
            raise ValueError('fetched_at requires timezone')
        return self


class MatchupBatch(StrictDTO):
    hero_id: int
    status: Literal['ok', 'not_found', 'rate_limited', 'unavailable', 'malformed']
    rows: tuple[MatchupStat, ...] = ()
    retry_after_seconds: int | None = None


class OpenDotaMatchups:
    """Bounded TTL cache, per-hero single-flight; shared 429 cooldown across heroes."""
    def __init__(self, client: OpenDotaClient, *, ttl_seconds: int = 3600,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if ttl_seconds <= 0:
            raise ValueError('TTL must be positive')
        self.client = client
        self.ttl = ttl_seconds
        self.clock = clock
        self.cache: dict[int, tuple[float, MatchupBatch]] = {}
        self.locks: dict[int, asyncio.Lock] = {}
        self.rate_limited_until = 0.0

    async def fetch(self, hero_id: int) -> MatchupBatch:
        if type(hero_id) is not int or not 0 < hero_id < 100000:
            raise ValueError('invalid hero ID')
        lock = self.locks.setdefault(hero_id, asyncio.Lock())
        async with lock:
            now = self.clock()
            if hero_id in self.cache and self.cache[hero_id][0] > now:
                return self.cache[hero_id][1]
            if now < self.rate_limited_until:
                return MatchupBatch(hero_id=hero_id, status='rate_limited',
                                    retry_after_seconds=max(1, int(self.rate_limited_until - now + .999)))
            status, body, retry = await self.client.get_json(f'/heroes/{hero_id}/matchups')
            if status == 429:
                delay = retry or 60
                self.rate_limited_until = self.clock() + delay
                result = MatchupBatch(hero_id=hero_id, status='rate_limited', retry_after_seconds=delay)
            elif status == 404:
                result = MatchupBatch(hero_id=hero_id, status='not_found')
            elif status != 200:
                result = MatchupBatch(hero_id=hero_id, status='unavailable')
            else:
                result = parse_matchups(hero_id, body, datetime.now(UTC))
            duration = self.ttl if result.status == 'ok' else result.retry_after_seconds or 60
            self.cache[hero_id] = (self.clock() + duration, result)
            # Bounded hero cache; old entries only affect performance, never correctness.
            for old in tuple(self.cache):
                if self.cache[old][0] <= self.clock():
                    self.cache.pop(old)
            if len(self.cache) > 256:
                self.cache.pop(next(iter(self.cache)))
            return result


def parse_matchups(hero_id: int, body: object, fetched_at: datetime) -> MatchupBatch:
    if not isinstance(body, list):
        return MatchupBatch(hero_id=hero_id, status='malformed')
    rows: list[MatchupStat] = []
    try:
        for row in body:
            if not isinstance(row, dict):
                raise ValueError('row is not an object')
            rows.append(MatchupStat.model_validate({
                'hero_id': hero_id, 'opponent_id': row.get('hero_id'), 'games_played': row.get('games_played'),
                'wins': row.get('wins'), 'fetched_at': fetched_at,
                'source_ref': f'https://api.opendota.com/api/heroes/{hero_id}/matchups',
            }))
        if len({r.opponent_id for r in rows}) != len(rows):
            raise ValueError('duplicate matchup')
    except (ValidationError, ValueError):
        return MatchupBatch(hero_id=hero_id, status='malformed')
    return MatchupBatch(hero_id=hero_id, status='ok', rows=tuple(sorted(rows, key=lambda r: r.opponent_id)))
