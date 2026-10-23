from typing import Literal
from importlib.resources import files
import json
from pydantic import Field, model_validator
from app.models.matches import StrictDTO
from app.models.draft import Axis

CONSTANTS = 'https://raw.githubusercontent.com/odota/dotaconstants/master/build/abilities.json'
MODE_SOURCE = 'https://raw.githubusercontent.com/odota/dotaconstants/master/build/game_mode.json'
PATCH_SOURCE = 'https://raw.githubusercontent.com/odota/dotaconstants/master/build/patch.json'
LOCAL_RULES = 'docs/DRAFT_ANALYZER_SPEC.md#rules-v1'
Tag = Literal[
    'save', 'dispel', 'control', 'initiation', 'aoe', 'illusions', 'physical', 'magical',
    'objectives', 'mobility', 'sustained', 'midgame', 'lategame', 'farm',
]


class VisibilityPolicy(StrictDTO):
    name: str
    game_mode: int
    patches: tuple[int, ...] = Field(min_length=1)
    kind: Literal['hidden_221', 'public_sequence']
    source_refs: tuple[str, ...] = Field(min_length=1)


class HeroProfile(StrictDTO):
    hero_id: int = Field(gt=0)
    name: str
    tags: tuple[Tag, ...]
    patches: tuple[int, ...] = Field(min_length=1)
    # A profile may describe a patch qualitatively without proving numerical mechanics for it.
    verified_numeric_patches: tuple[int, ...] = ()
    source_refs: tuple[str, ...] = Field(min_length=1)


class HeroDescriptor(StrictDTO):
    """Source classifications, not verified positions or numerical scoring inputs."""
    hero_id: int = Field(gt=0)
    name: str
    roles: tuple[str, ...]
    attack_type: Literal['Melee', 'Ranged']
    source_ref: str
    patch_scope: Literal['snapshot_unverified'] = 'snapshot_unverified'


class InteractionRule(StrictDTO):
    code: str
    kind: Literal['synergy', 'counter']
    actor_tag: Tag
    target_tag: Tag
    utility: float = Field(ge=0, le=100)
    text: str
    patches: tuple[int, ...]
    verified_numeric_patches: tuple[int, ...] = ()
    directionality: Literal['symmetric', 'directed'] = 'symmetric'
    source_refs: tuple[str, ...] = Field(min_length=1)


def default_weights() -> dict[Axis, float]:
    return {'matchup': .30, 'synergy': .25, 'balance': .20, 'phase': .15, 'win_condition': .10}


class DraftConfig(StrictDTO):
    model_version: str = 'draft-heuristic-v1.1.1'
    weights: dict[Axis, float] = Field(default_factory=default_weights)
    minimum_coverage: float = Field(default=.55, gt=0, le=1)
    minimum_axes: int = Field(default=2, ge=1, le=5)
    minimum_matchup_games: int = Field(default=100, ge=1)
    prior_games: int = Field(default=200, ge=1)
    matchup_effect_threshold: float = Field(default=3, gt=0, le=50)
    even_margin: float = Field(default=5, ge=0, le=100)
    composition_present: float = Field(default=75, ge=0, le=100)
    composition_absent: float = Field(default=25, ge=0, le=100)
    grade_boundaries: tuple[float, float, float] = (35., 50., 70.)
    profiles: tuple[HeroProfile, ...] = ()
    catalog: tuple[HeroDescriptor, ...] = ()
    policies: tuple[VisibilityPolicy, ...] = ()
    rules: tuple[InteractionRule, ...] = ()

    @model_validator(mode='after')
    def validate_config(self) -> 'DraftConfig':
        if not 0 <= self.grade_boundaries[0] < self.grade_boundaries[1] < self.grade_boundaries[2] <= 100:
            raise ValueError('grade boundaries must be strictly increasing')
        expected = {'matchup', 'synergy', 'balance', 'phase', 'win_condition'}
        if set(self.weights) != expected or any(v <= 0 for v in self.weights.values()) or abs(sum(self.weights.values()) - 1) > 1e-9:
            raise ValueError('weights must contain all five axes and sum to one')
        if len({p.hero_id for p in self.profiles}) != len(self.profiles):
            raise ValueError('duplicate hero profile')
        if len({p.hero_id for p in self.catalog}) != len(self.catalog):
            raise ValueError('duplicate catalog hero')
        if len({r.code for r in self.rules}) != len(self.rules):
            raise ValueError('duplicate reason code')
        if any(not set(p.verified_numeric_patches).issubset(p.patches) for p in self.profiles):
            raise ValueError('verified profile patch must be declared')
        if any(not set(r.verified_numeric_patches).issubset(r.patches) for r in self.rules):
            raise ValueError('verified rule patch must be declared')
        keys = [(p.game_mode, patch) for p in self.policies for patch in p.patches]
        if len(keys) != len(set(keys)):
            raise ValueError('ambiguous visibility policies')
        return self


def default_config() -> DraftConfig:
    # Qualitative capability review, not a complete hero database. No inference across patches.
    definitions: tuple[tuple[int, str, str, tuple[Tag, ...]], ...] = (
        (111, 'Oracle', 'oracle', ('save', 'dispel', 'magical', 'control')),
        (123, 'Hoodwink', 'hoodwink', ('control', 'physical', 'magical', 'mobility', 'midgame')),
        (81, 'Chaos Knight', 'chaosknight', ('illusions', 'physical', 'control', 'sustained', 'farm', 'lategame')),
        (43, 'Death Prophet', 'deathprophet', ('objectives', 'physical', 'magical', 'sustained', 'midgame')),
        (67, 'Spectre', 'spectre', ('illusions', 'physical', 'mobility', 'farm', 'lategame')),
        (7, 'Earthshaker', 'earthshaker', ('aoe', 'control', 'initiation', 'magical', 'midgame')),
        (1, 'Anti-Mage', 'antimage', ('physical', 'mobility', 'farm', 'lategame')),
        (5, 'Crystal Maiden', 'crystalmaiden', ('control', 'aoe', 'magical', 'midgame')),
        (25, 'Lina', 'lina', ('control', 'magical', 'physical', 'midgame')),
        (29, 'Tidehunter', 'tidehunter', ('initiation', 'control', 'aoe', 'magical', 'midgame')),
        (27, 'Shadow Shaman', 'shadowshaman', ('control', 'objectives', 'magical', 'midgame')),
    )
    profiles = tuple(HeroProfile(
        hero_id=hid, name=name, tags=tags, patches=(60,),
        source_refs=(f'https://www.dota2.com/hero/{slug}', CONSTANTS),
    ) for hid, name, slug, tags in definitions)
    rules = (
        InteractionRule(code='save_sustained', kind='synergy', actor_tag='save', target_tag='sustained', utility=75.,
                        text='Сейв помогает союзнику продолжить длительную атаку; важны дистанция и момент применения.',
                        patches=(60,), source_refs=(CONSTANTS, LOCAL_RULES)),
        InteractionRule(code='control_followup', kind='synergy', actor_tag='control', target_tag='magical', utility=65.,
                        text='Контроль создаёт окно для магического урона союзника.',
                        patches=(60,), source_refs=(CONSTANTS, LOCAL_RULES)),
        InteractionRule(code='initiation_aoe', kind='synergy', actor_tag='initiation', target_tag='aoe', utility=75.,
                        text='Инициация создаёт возможность для массового урона; требуется согласовать применение способностей.',
                        patches=(60,), source_refs=(CONSTANTS, LOCAL_RULES)),
        InteractionRule(code='aoe_illusions', kind='counter', actor_tag='aoe', target_tag='illusions', utility=70.,
                        text='Массовый урон помогает против группы иллюзий; эффект зависит от расположения и защиты целей.',
                        patches=(60,), source_refs=(CONSTANTS, LOCAL_RULES)),
    )
    catalog_data = json.loads(files('app').joinpath('data/hero_catalog.json').read_text())
    catalog = tuple(HeroDescriptor.model_validate({
        'hero_id': row['hero_id'], 'name': row['name'], 'roles': tuple(row['roles']),
        'attack_type': row['attack_type'], 'source_ref': catalog_data['source_ref'],
    })
                    for row in catalog_data['heroes'])
    return DraftConfig(profiles=profiles, catalog=catalog, rules=rules, policies=(VisibilityPolicy(
        name='ranked-all-pick-7.27-221', game_mode=22, patches=(46,), kind='hidden_221',
        source_refs=('https://www.dota2.com/patches/7.27', MODE_SOURCE, PATCH_SOURCE),
    ),))
