from collections import Counter
from dataclasses import dataclass

from app.models.draft import PickVisibility
from app.models.matches import DraftAction, NormalizedMatch, Team
from app.services.draft.config import DraftConfig


@dataclass(frozen=True)
class Sequence:
    policy: str
    actions: tuple[DraftAction, ...]
    visibility: dict[int, PickVisibility]
    issues: tuple[str, ...]

    @property
    def sequential(self) -> bool:
        return bool(self.visibility)


def resolve_sequence(match: NormalizedMatch, config: DraftConfig) -> Sequence:
    raw = match.raw.draft
    actions = raw.actions
    issues: list[str] = []
    if not raw.available or not actions:
        issues.append('draft_order_unavailable')
    # Revalidate rather than trusting completeness flags or model_copy callers.
    orders = [a.order for a in actions]
    if any(a.order is None or a.is_pick is None or a.hero_id is None or a.team is None for a in actions):
        issues.append('invalid_action')
    if any(a.team_code is None or {0: Team.RADIANT, 1: Team.DIRE}.get(a.team_code) != a.team for a in actions):
        issues.append('inconsistent_team_code')
    if sorted(o for o in orders if o is not None) != list(range(len(actions))):
        issues.append('incomplete_or_duplicate_order')
    if len({a.source_order for a in actions}) != len(actions):
        issues.append('duplicate_source_order')
    roster = [(p.team, p.hero_id) for p in match.players]
    if len(roster) != 10 or Counter(t for t, _ in roster) != {Team.RADIANT: 5, Team.DIRE: 5}:
        issues.append('incomplete_roster')
    if any(h is None for _, h in roster) or len({h for _, h in roster}) != len(roster):
        issues.append('invalid_roster')
    picks = [(a.team, a.hero_id) for a in actions if a.is_pick is True]
    if Counter(picks) != Counter(roster):
        issues.append('picks_roster_mismatch')
    banned = [a.hero_id for a in actions if a.is_pick is False]
    if len(banned) != len(set(banned)) or set(banned) & {h for _, h in picks}:
        issues.append('contradictory_bans')
    policies = [p for p in config.policies if p.game_mode == match.summary.game_mode and match.summary.patch in p.patches]
    if not policies:
        issues.append('visibility_policy_not_verified')
    if issues:
        return Sequence('final-only', actions, {}, tuple(dict.fromkeys(issues)))
    policy = policies[0]
    ordered = tuple(sorted(actions, key=lambda a: a.order if a.order is not None else -1))
    stages: dict[int, int] = {}
    counts = {Team.RADIANT: 0, Team.DIRE: 0}
    for action in ordered:
        if action.is_pick and action.team is not None:
            index = counts[action.team]
            stages[action.source_order] = 1 if index < 2 else 2 if index < 4 else 3
            counts[action.team] += 1
    if policy.kind == 'hidden_221':
        pick_stages = [stages[a.source_order] for a in ordered if a.is_pick]
        # A later round cannot occur before both teams finish the previous round.
        if pick_stages != sorted(pick_stages):
            return Sequence('final-only', actions, {}, ('inconsistent_round_order',))
        # All-pick bans are before picking; don't guess reveal time for interleaved bans.
        seen_pick = False
        for a in ordered:
            if a.is_pick:
                seen_pick = True
            elif seen_pick:
                return Sequence('final-only', actions, {}, ('interleaved_all_pick_bans',))
    views: dict[int, PickVisibility] = {}
    for index, action in enumerate(ordered):
        if not action.is_pick:
            continue
        before = ordered[:index]
        stage = stages[action.source_order] if policy.kind == 'hidden_221' else None
        own = tuple(a.hero_id for a in before if a.is_pick and a.team == action.team and a.hero_id is not None)
        enemies = tuple(a.hero_id for a in before if a.is_pick and a.team != action.team and a.hero_id is not None
                        and (policy.kind == 'public_sequence' or stages[a.source_order] < stages[action.source_order]))
        bans = tuple(a.hero_id for a in before if a.is_pick is False and a.hero_id is not None)
        views[action.source_order] = PickVisibility(
            own_known_picks_before=own, enemy_revealed_before=enemies,
            enemy_hidden_or_unknown=5 - len(enemies), bans_known_before=bans,
            stage_index=stage, sequence_confidence='high',
        )
    return Sequence(policy.name, ordered, views, ())
