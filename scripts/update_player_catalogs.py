"""Refresh reviewed player display catalogs from one pinned dotaconstants revision.

Change REVISION only after reviewing the new upstream data and match-patch scope.
Run from the repository root: .venv/bin/python scripts/update_player_catalogs.py
"""
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

REVISION = '5c0242df9057848fa2036ca3fafe9f2bd4508163'
SOURCE = f'https://raw.githubusercontent.com/odota/dotaconstants/{REVISION}/build/'
CDN = 'https://cdn.cloudflare.steamstatic.com'
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'backend/app/data'


def read(name: str) -> dict:
    with urlopen(SOURCE + name, timeout=30) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise ValueError(f'{name} must be an object')
    return value


def image_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    path = urlsplit(value).path
    if not path.startswith('/apps/dota2/images/dota_react/') or not path.endswith('.png'):
        return None
    return CDN + path


def main() -> None:
    heroes = read('heroes.json')
    item_ids = read('item_ids.json')
    items = read('items.json')
    hero_file = DATA / 'hero_catalog.json'
    existing = json.loads(hero_file.read_text())
    if existing['revision'] != REVISION:
        raise ValueError('review the existing hero revision before changing it')
    for row in existing['heroes']:
        source = heroes.get(str(row['hero_id']))
        if not isinstance(source, dict) or source.get('localized_name') != row['name']:
            raise ValueError(f'hero catalog mismatch: {row["hero_id"]}')
        row['image_url'] = image_url(source.get('img'))
    output = []
    for raw_id, key in sorted(item_ids.items(), key=lambda pair: int(pair[0])):
        item_id = int(raw_id)
        if item_id < 0 or not isinstance(key, str) or not key:
            raise ValueError(f'invalid item mapping: {raw_id}')
        metadata = items.get(key)
        if isinstance(metadata, dict) and metadata.get('id') != item_id:
            raise ValueError(f'item catalog mismatch: {item_id}')
        name = metadata.get('dname') if isinstance(metadata, dict) else None
        output.append({
            'item_id': item_id,
            'name': name if isinstance(name, str) and name.strip() else None,
            'image_key': key,
            'image_url': image_url(metadata.get('img')) if isinstance(metadata, dict) else None,
        })
    item_catalog = {
        'revision': REVISION, 'patch_scope': 'snapshot_unverified',
        'source_refs': [SOURCE + 'item_ids.json', SOURCE + 'items.json'],
        'items': output,
    }
    hero_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + '\n')
    (DATA / 'item_catalog.json').write_text(json.dumps(item_catalog, ensure_ascii=False, indent=2) + '\n')
    print(f'heroes={len(existing["heroes"])} items={len(output)} named={sum(bool(row["name"]) for row in output)}')


if __name__ == '__main__':
    main()
