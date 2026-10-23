from app.services.player_catalog import hero_catalog, item_catalog, resolve_item


def test_pinned_catalogs_cover_known_heroes_and_items() -> None:
    hero_revision, heroes = hero_catalog()
    item_revision, items = item_catalog()
    assert hero_revision == item_revision == '5c0242df9057848fa2036ca3fafe9f2bd4508163'
    assert len(heroes) == 127 and len(items) == 596
    assert heroes[123]['name'] == 'Hoodwink'
    assert heroes[123]['image_url'].endswith('/hoodwink.png')
    blink = resolve_item(1)
    assert blink is not None and blink.name == 'Blink Dagger'
    assert blink.image_key == 'blink'
    assert blink.image_url is not None and blink.image_url.endswith('/blink.png')


def test_empty_missing_and_unknown_items_are_distinct() -> None:
    empty = resolve_item(0)
    assert empty is not None and empty.status == 'empty' and empty.name is None
    assert resolve_item(None) is None
    unknown = resolve_item(999999)
    assert unknown is not None and unknown.status == 'unmapped'
    assert unknown.item_id == 999999 and unknown.name is None
