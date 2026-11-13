"""Shared mutable battle state; configuration remains immutable."""

from dataclasses import dataclass, field, asdict
from copy import deepcopy, copy


@dataclass
class BuffInstance:
    id: str
    name: str
    source_character: int
    source_equipment_id: str
    source_equipment_name: str
    source_slot: str
    target_character: int
    attribute: str
    amount: float
    source_stats: dict
    applied_at: float = 0.0
    duration: float | None = None
    stacks: int = 1
    max_stacks: int = 1
    expires_at: float | None = None


@dataclass
class PeriodicDebuff:
    id: str
    name: str
    source_character: int
    applied_at: float = 0.0
    interval: float = 1.0
    maximum_hp_ratio: float = 0.05
    next_tick_at: float = 1.0


@dataclass
class CharacterState:
    index: int
    name: str
    job: str
    enabled: bool
    base_stats: dict
    stats: dict
    equipment: dict
    domain_ring: dict | None = None
    ring_gain_amount: float = 0.0
    ring_next_tick: float = 1.0
    regeneration_buffs: list = field(default_factory=list)
    negative_immunities: dict = field(default_factory=dict)
    buffs: list[BuffInstance] = field(default_factory=list)
    alive: bool = True
    next_action_at: float = 1.5
    last_action_at: float | None = None
    last_skill_cooldown: float = 0.0
    first_strike: bool = False
    maximum_hp: float | None = None
    current_hp: float | None = None
    debuffs: list[PeriodicDebuff] = field(default_factory=list)


@dataclass
class ContractState:
    name: str
    owner_index: int
    skill_multiplier: float
    interval: float = 14.0
    clock_start_at: float = 0.1
    next_tick_at: float = 14.1
    total_damage: float = 0.0
    active: bool = True
    ticks: int = 0


@dataclass
class BattleState:
    characters: list[CharacterState]
    target: dict
    time: float = 0.0
    events: list[dict] = field(default_factory=list)
    contract: ContractState | None = None
    target_current_hp: float | None = None
    discarded_event_count: int = 0

    def to_dict(self):
        return deepcopy(asdict(self))


def clone_for_resolution(state):
    """Copy only mutable resolution state; buff records and configs are read-only.

    Buff deltas are replaced as new records, never edited. Periodic debuff timers
    and the contract are mutable and therefore receive independent copies.
    """
    draft = copy(state)
    draft.characters = []
    for original in state.characters:
        character = copy(original)
        character.stats = original.stats.copy()
        character.negative_immunities = original.negative_immunities.copy()
        character.regeneration_buffs = deepcopy(original.regeneration_buffs)
        character.buffs = list(original.buffs)
        character.debuffs = [copy(debuff) for debuff in original.debuffs]
        draft.characters.append(character)
    draft.contract = copy(state.contract) if state.contract is not None else None
    draft.events = list(state.events)
    return draft
