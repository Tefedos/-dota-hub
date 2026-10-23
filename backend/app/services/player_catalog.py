"""Pinned display metadata for the public players report."""
import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from app.models.match_api import PublicItem


@lru_cache(maxsize=1)
def hero_catalog() -> tuple[str, dict[int, dict[str, Any]]]:
    data = json.loads(files('app').joinpath('data/hero_catalog.json').read_text())
    return data['revision'], {row['hero_id']: row for row in data['heroes']}


@lru_cache(maxsize=1)
def item_catalog() -> tuple[str, dict[int, dict[str, Any]]]:
    data = json.loads(files('app').joinpath('data/item_catalog.json').read_text())
    return data['revision'], {row['item_id']: row for row in data['items']}


@lru_cache(maxsize=1)
def match_metadata_catalog() -> tuple[str, dict[int, str], dict[int, str]]:
    data = json.loads(files('app').joinpath('data/match_metadata_catalog.json').read_text())
    modes = {int(key): row['name'] for key, row in data['game_modes'].items()}
    patches = {int(key): name for key, name in data['patches'].items()}
    return data['revision'], modes, patches


def resolve_item(item_id: int | None) -> PublicItem | None:
    if item_id is None:
        return None
    if item_id == 0:
        return PublicItem(item_id=0, status='empty')
    _, items = item_catalog()
    row = items.get(item_id)
    if row is None:
        return PublicItem(item_id=item_id, status='unmapped')
    name = row['name']
    return PublicItem(
        item_id=item_id, name=name, image_key=row['image_key'], image_url=row['image_url'],
        status='known' if name else 'unmapped',
    )
