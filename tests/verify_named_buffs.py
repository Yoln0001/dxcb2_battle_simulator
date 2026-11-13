from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.initialization import initialize_battle, BattleConfigurationError
from engine.runtime.buffs import apply_named_buff, expire_buffs
from engine.runtime.amplification import attack_snapshot

config = {
    "characters": [
        {
            "name": f"角色{i + 1}",
            "job": "岩浆法师" if i == 0 else "寒霜法师",
            "enabled": True,
            "stats": {
                "magic": 10000,
                "strength": 100,
                "technique": 1000 if i == 0 else 2000,
                "speed": 100,
            },
            "equipment": {},
        }
        for i in range(4)
    ]
}
config["characters"][0]["equipment"] = {"weapon": "start"}
equipment = {
    "start": {
        "id": "start",
        "name": "开战杖",
        "effectName": "开战魔力",
        "category": "weapon",
        "weaponJob": "法师",
        "startingBuff": {
            "enabled": True,
            "recipient": "self",
            "coefficients": {"strength": 0, "magic": 1, "technique": 0, "speed": 0},
            "target": "magic",
        },
    }
}
state = initialize_battle(config, equipment)


def heart(now):
    return apply_named_buff(
        state,
        name="影兽之心",
        source_index=1,
        target_indices=[1],
        conversions={"magic": {"magic": 0.12}},
        now=now,
        max_stacks=5,
    )


first = heart(1)[0]
assert first.amount == 2400 and first.stacks == 1
assert state.characters[0].stats["magic"] == 22400
second = heart(2)[0]
assert second.amount == 4800 and second.stacks == 2
assert second.source_stats["magic"] == 20000
assert state.characters[0].stats["magic"] == 24800
assert len([b for b in state.characters[0].buffs if b.name == "影兽之心"]) == 1
for t in (3, 4, 5, 6):
    heart(t)
assert state.characters[0].stats["magic"] == 32000
assert [b for b in state.characters[0].buffs if b.name == "影兽之心"][0].stacks == 5
assert [b for b in state.characters[0].buffs if b.name == "开战魔力"][0].amount == 10000
before = deepcopy(state.to_dict())
action = attack_snapshot(
    state.characters[0],
    [
        {
            "kind": "amplify",
            "conversions": [{"target": "magic", "enabled": True, "coefficients": {"magic": 1}}],
        }
    ],
)
assert action["magic"] == 64000 and state.to_dict() == before


# Same name, different caster: overwrite even though sources differ; refresh 15s.
def focus(source, time):
    return apply_named_buff(
        state,
        name="凝神静气",
        source_index=source,
        target_indices=[1, 2, 3, 4],
        conversions={"technique": {"technique": 0.5}},
        now=time,
        duration=15,
        max_stacks=1,
    )


focus(1, 7)
assert state.characters[2].stats["technique"] == 2500
focus(1, 10)
assert state.characters[2].stats["technique"] == 2500
assert [b for b in state.characters[2].buffs if b.name == "凝神静气"][0].expires_at == 25
focus(2, 12)
assert state.characters[2].stats["technique"] == 3000
buff = [b for b in state.characters[2].buffs if b.name == "凝神静气"][0]
assert buff.amount == 1000 and buff.source_character == 2 and buff.expires_at == 27
expire_buffs(state, 26.999)
assert state.characters[2].stats["technique"] == 3000
expire_buffs(state, 27)
assert state.characters[2].stats["technique"] == 2000
assert state.characters[0].stats["magic"] == 32000
focus(1, 30)
expire_buffs(state, 45)
focus(1, 45)
assert [b for b in state.characters[0].buffs if b.name == "凝神静气"][0].expires_at == 60
before = deepcopy(state.to_dict())
try:
    apply_named_buff(
        state,
        name="凝神静气",
        source_index=1,
        target_indices=[1, 2, 3, 4],
        conversions={"technique": {"missing": 1}},
        now=46,
        duration=15,
    )
except BattleConfigurationError:
    pass
else:
    raise AssertionError("missing coefficient source must fail")
assert state.to_dict() == before
print(
    "PASS: 20000->22400->24800, recorded 2400/4800 deltas, five-layer cap, cross-caster overwrite, refreshed 15s expiry, exact-time expiration, unrelated buffs and atomic failure"
)
