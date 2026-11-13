from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.initialization import initialize_battle, BattleConfigurationError
from engine.runtime.buffs import apply_named_buff, expire_buffs
from engine.runtime.cooldowns import strength_speed_ratio, action_cooldown, schedule_after_action
from engine.runtime.amplification import attack_snapshot

assert strength_speed_ratio(300, 0, 99) == 3
assert strength_speed_ratio(399, 0, 99) == 3
assert strength_speed_ratio(400, 0, 99) == 3
assert strength_speed_ratio(0, 10, 9) == 0.1
assert strength_speed_ratio(0, 10, 99) == 0
assert strength_speed_ratio(0.3, 0, 0) == 1  # numerator has minimum 1
assert strength_speed_ratio(3, 0, 9) == 0.3
assert strength_speed_ratio(199, 0, 99) == 1.9
config = {
    "characters": [
        {
            "enabled": True,
            "stats": {"strength": 1000, "unload": 200, "speed": 999, "magic": 10000},
            "equipment": {},
        }
        for _ in range(4)
    ]
}
state = initialize_battle(config, {})
assert all(c.next_action_at == 2.3 for c in state.characters)
assert action_cooldown(state.characters[0], 1.8) == {
    "fixed": 1.5,
    "skill": 1.8,
    "strength_speed_ratio": 0.8,
    "total": 4.1,
}
try:
    schedule_after_action(state, 1, 1.8)
except BattleConfigurationError:
    pass
else:
    raise AssertionError("first action must wait 1.5 seconds plus ratio")
expire_buffs(state, 2.3)
schedule_after_action(state, 1, 1.8)
assert state.characters[0].next_action_at == 6.4
apply_named_buff(
    state,
    name="力量增幅",
    source_index=1,
    target_indices=[1],
    conversions={"strength": {"strength": 0.5}},
    now=3,
    max_stacks=1,
)
from engine.runtime.cooldowns import check_action_ready

assert check_action_ready(state.characters[0], 3)["next_action_at"] == 6.9
assert action_cooldown(state.characters[0], 1.8)["strength_speed_ratio"] == 1.3
attack_snapshot(
    state.characters[0],
    [
        {
            "kind": "amplify",
            "conversions": [
                {"target": "strength", "enabled": True, "coefficients": {"strength": 1}}
            ],
        }
    ],
)
assert action_cooldown(state.characters[0], 1.8)["strength_speed_ratio"] == 1.3
expire_buffs(state, 6.9)
schedule_after_action(state, 1, 1.8)
assert state.characters[0].next_action_at == 11.5
print(
    "PASS: first 1.5s+ratio action, fixed+skill+ratio, numerator minimum, floor-to-tenth boundaries, persistent buff effects, temporary isolation and scheduling"
)

equipment = {
    "id": "start",
    "name": "力量装备",
    "category": "accessory",
    "startingBuff": {
        "enabled": True,
        "target": "strength",
        "recipient": "self",
        "coefficients": {"strength": 1, "magic": 0, "technique": 0, "speed": 0},
    },
}
config["characters"][0]["equipment"] = {"accessory1": "start"}
state = initialize_battle(config, {"start": equipment})
assert state.characters[0].next_action_at == 3.3
assert state.characters[1].next_action_at == 2.3
print("PASS: first action uses final opening-buff attributes")

assert action_cooldown(state.characters[0], -10)["total"] == 0.5
assert action_cooldown(state.characters[0], -2)["total"] == 1.3
state.time = state.characters[0].next_action_at
schedule_after_action(state, 1, -10)
assert state.characters[0].next_action_at == state.time + 0.5
try:
    schedule_after_action(state, 1, -10)
    raise AssertionError("second action accepted before cooldown ends")
except BattleConfigurationError:
    pass
from backend.skills.store import cooldown_number

assert cooldown_number(-2) == -2
print("PASS: ratio capped at 3, negative skill cooldown, 0.5s minimum, no early action")
