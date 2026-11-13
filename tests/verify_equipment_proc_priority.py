from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.simulation import SingleBattle

config = {
    "battle": {"duration": 2},
    "target": {"speed": 100},
    "characters": [
        {
            "enabled": True,
            "job": "寒霜法师",
            "stats": {"constitution": 100, "magic": 100, "strength": 0, "speed": 99},
            "equipment": {},
            "skillGroup": "g",
        }
        for _ in range(4)
    ],
}
skill = {
    "id": "s",
    "name": "技能",
    "job": "寒霜法师",
    "damageType": "magic",
    "cooldown": 0,
    "coefficients": {"magic": 1},
}
group = {
    "job": "寒霜法师",
    "entry": "n",
    "subgroups": [
        {"id": "sub", "nextGroup": "sub", "skills": [{"id": "n", "skillId": "s", "next": ""}]}
    ],
}
slots = ["weapon", "armor", "accessory1", "accessory2", "stone"]
items = {}
for slot in slots:
    items[slot] = {
        "id": slot,
        "name": slot,
        "category": "accessory" if slot.startswith("accessory") else slot,
        "weaponJob": "",
        "startingBuff": {"enabled": False},
        "triggerEnabled": True,
        "triggerEffects": [
            {
                "name": slot,
                "triggerType": "magic",
                "probability": 100,
                "effect": {"kind": "immediateAction"},
            }
        ],
    }
config["characters"][0]["equipment"] = {slot: slot for slot in slots}
battle = SingleBattle(config, items, {"s": skill}, {"g": group}, seed=1)


class Rolls:
    def __init__(self, values):
        self.values = iter(values)
        self.count = 0

    def random(self):
        self.count += 1
        return next(self.values)


for position in range(5):
    for i, slot in enumerate(slots):
        items[slot]["triggerEffects"][0]["probability"] = 0 if i < position else 100
    battle.rng = Rolls([0.5] * (position + 1))
    result = battle.procs(battle.state.characters[0], skill)
    assert len(result) == 1 and result[0][1] == slots[position]
    assert battle.rng.count == position + 1
# Trigger type mismatches are skipped without consuming a roll.
items["weapon"]["triggerEffects"][0]["probability"] = 100
items["weapon"]["triggerEffects"][0]["triggerType"] = "physical"
items["armor"]["triggerEffects"][0]["probability"] = 100
battle.rng = Rolls([0.5])
assert battle.procs(battle.state.characters[0], skill)[0][1] == "armor"
assert battle.rng.count == 1
# Multiple rows in one equipment still yield at most one successful effect.
items["weapon"]["triggerEffects"] = [
    {
        "name": "first",
        "triggerType": "magic",
        "probability": 0,
        "effect": {"kind": "immediateAction"},
    },
    {
        "name": "second",
        "triggerType": "magic",
        "probability": 100,
        "effect": {"kind": "immediateAction"},
    },
]
battle.rng = Rolls([0.5, 0.5])
result = battle.procs(battle.state.characters[0], skill)
assert len(result) == 1 and result[0][2]["name"] == "second" and battle.rng.count == 2
print(
    "PASS: weapon/armor/accessory1/accessory2/stone priority, one proc per action, no later rolls, trigger-type filtering"
)
