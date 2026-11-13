from pathlib import Path
import copy, sys, tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.api.bosses import validate_boss_group, BossStore
from backend.skills.store import SkillError
from engine.runtime.simulation import SkillSequence

legacy = {
    "name": "Legacy",
    "skills": [
        {"name": "Hit", "damageType": "physical", "baseValue": 10},
        {"name": "Fire", "damageType": "magic", "baseValue": 20},
    ],
}
old = validate_boss_group(legacy)
assert len(old["subgroups"]) == 1 and old["subgroups"][0]["nextGroup"] == old["subgroups"][0]["id"]
assert [n["skillId"] for n in old["subgroups"][0]["skills"]] == [s["id"] for s in old["skills"]]
assert validate_boss_group(old) == old
new = copy.deepcopy(old)
new["entry"] = "a"
new["subgroups"] = [
    {
        "id": "g1",
        "nextGroup": "g2",
        "skills": [
            {
                "id": "a",
                "skillId": old["skills"][0]["id"],
                "next": "c",
                "targetSelection": "random",
            },
            {"id": "b", "skillId": "__wait__", "waitDuration": 2},
        ],
    },
    {
        "id": "g2",
        "nextGroup": "g2",
        "skills": [
            {"id": "c", "skillId": old["skills"][1]["id"], "targetSelection": "highestArmor"}
        ],
    },
]
validated = validate_boss_group(new)
skills = {s["id"]: {**s, "job": "Boss"} for s in validated["skills"]}
sequence = SkillSequence({**validated, "job": "Boss"}, skills, "Boss")
assert sequence.current == "a"
sequence.advance()
assert sequence.current == "c"
sequence.advance()
assert sequence.current == "c"
# Skill jump is unconditional and precedes the group-end transition.
assert all(c is None for c in sequence.conditions.values())
without_jump = copy.deepcopy(new)
without_jump["subgroups"][0]["skills"][0]["next"] = ""
v = validate_boss_group(without_jump)
sequence = SkillSequence({**v, "job": "Boss"}, skills, "Boss")
sequence.advance()
assert sequence.current == "b"
sequence.advance()
assert sequence.current == "c"
stop = copy.deepcopy(new)
stop["subgroups"][1]["nextGroup"] = ""
v = validate_boss_group(stop)
sequence = SkillSequence({**v, "job": "Boss"}, skills, "Boss")
sequence.advance()
sequence.advance()
assert sequence.current == ""
for mutate in (
    lambda g: g["subgroups"][0]["skills"][0].update(next="missing"),
    lambda g: g["subgroups"][0].update(nextGroup="missing"),
    lambda g: g["subgroups"][0]["skills"][0].update(skillId="other-boss-skill"),
    lambda g: g["subgroups"][0]["skills"][0].update(jumpCondition={"effectIndex": 0}),
    lambda g: g["subgroups"][0]["skills"][1].update(waitDuration=0),
):
    bad = copy.deepcopy(new)
    mutate(bad)
    try:
        validate_boss_group(bad)
    except SkillError:
        pass
    else:
        raise AssertionError("invalid Boss graph accepted")
with tempfile.TemporaryDirectory() as folder:
    store = BossStore(Path(folder) / "bosses.json")
    saved = store.save({"name": "Boss", "attributes": {"constitution": 100}, "skillGroup": new})[
        "item"
    ]
    assert store.read()["bosses"][0]["skillGroup"] == saved["skillGroup"] == validated
print(
    "PASS: legacy Boss loop migration, multiple subgroups, repeated skills, direct and group-end jumps, stop/self-loop semantics, reference validation and save/reload"
)

from engine.runtime.boss_sequence import BossSkillSequence
from types import SimpleNamespace
import random

conditional = copy.deepcopy(new)
conditional["subgroups"][0].update(type="conditional", nextGroup="g1")
a, b = conditional["subgroups"][0]["skills"]
a["next"] = ""
a["releaseCondition"] = {"kind": "bossHealthBelow", "threshold": 50}
b["releaseCondition"] = {"kind": "always"}
v = validate_boss_group(conditional)
seq = BossSkillSequence(v)
assert seq.choose_for_action(boss_hp=49, boss_max_hp=100)["name"] == "Hit"
seq.advance()
assert seq.current == "a"
assert seq.choose_for_action(boss_hp=50, boss_max_hp=100)["name"] == "等待"
seq.advance()
assert seq.current == "a"
for kind, args, match in [
    ("bossHealthAbove", {"boss_hp": 51, "boss_max_hp": 100}, True),
    ("timeAtLeast", {"time": 50}, True),
    ("timeAtLeast", {"time": 49}, False),
    ("enemyHealthBelow", {}, True),
    ("noEnemyHealthBelow", {}, False),
]:
    conditional["subgroups"][0]["skills"][0]["releaseCondition"] = {"kind": kind, "threshold": 50}
    seq = BossSkillSequence(validate_boss_group(conditional))
    players = [SimpleNamespace(enabled=True, alive=True, maximum_hp=100, current_hp=40)]
    assert (seq.choose_for_action(players, **args)["name"] == "Hit") == match
# First matching if wins, else if comes before the fallback.
conditional["subgroups"][0]["skills"].insert(
    1,
    {
        "id": "elif",
        "skillId": old["skills"][1]["id"],
        "releaseCondition": {"kind": "timeAtLeast", "threshold": 10},
    },
)
conditional["subgroups"][0]["skills"][0]["releaseCondition"] = {
    "kind": "bossHealthBelow",
    "threshold": 50,
}
seq = BossSkillSequence(validate_boss_group(conditional))
assert seq.choose_for_action(boss_hp=40, boss_max_hp=100, time=20)["name"] == "Hit"
seq = BossSkillSequence(validate_boss_group(conditional))
assert seq.choose_for_action(boss_hp=80, boss_max_hp=100, time=20)["name"] == "Fire"
random_group = copy.deepcopy(new)
random_group["subgroups"][0].update(type="random", nextGroup="g1")
random_group["subgroups"][0]["skills"][0]["next"] = ""
random_group["subgroups"][0]["skills"][1]["skillId"] = old["skills"][1]["id"]
v = validate_boss_group(random_group)


def sample():
    seq = BossSkillSequence(v, rng=random.Random(123))
    values = []
    for _ in range(100):
        values.append(seq.choose_for_action()["name"])
        seq.advance()
        assert seq.current == "a"
    return values


assert sample() == sample() and set(sample()) == {"Hit", "Fire"}
random_group["subgroups"][0]["skills"][0]["next"] = "c"
seq = BossSkillSequence(validate_boss_group(random_group), rng=random.Random(1))
assert seq.choose_for_action()["name"] == "Hit"
seq.advance()
assert seq.current == "c"
for mutate in (
    lambda g: g["subgroups"][0].update(type="invalid"),
    lambda g: g["subgroups"][0]["skills"][-1].update(
        releaseCondition={"kind": "timeAtLeast", "threshold": 10}
    ),
    lambda g: g["subgroups"][0]["skills"][0].update(
        releaseCondition={"kind": "bossHealthBelow", "threshold": 101}
    ),
):
    bad = copy.deepcopy(conditional)
    mutate(bad)
    try:
        validate_boss_group(bad)
    except SkillError:
        pass
    else:
        raise AssertionError("invalid mode or condition accepted")
with tempfile.TemporaryDirectory() as folder:
    store = BossStore(Path(folder) / "bosses.json")
    saved = store.save(
        {"name": "Boss", "attributes": {"constitution": 100}, "skillGroup": conditional}
    )["item"]
    assert store.read()["bosses"][0]["skillGroup"] == saved["skillGroup"]
print(
    "PASS: Boss if/else priority, HP/time conditions, random candidates, deterministic RNG, unconditional jumps and condition persistence"
)

assert len(v["subgroups"][0]["skills"]) == 1
assert v["subgroups"][0]["skills"][0]["skillIds"] == [s["id"] for s in old["skills"]]
assert validate_boss_group(v) == v
for candidates in ([], ["missing"], [old["skills"][0]["id"]] * 2, ["__wait__"]):
    bad = copy.deepcopy(v)
    bad["subgroups"][0]["skills"][0]["skillIds"] = candidates
    try:
        validate_boss_group(bad)
    except SkillError:
        pass
    else:
        raise AssertionError("invalid random candidates accepted")
legacy_random = copy.deepcopy(random_group)
legacy_random["entry"] = "b"
legacy_random["subgroups"][1]["skills"][0]["next"] = "b"
migrated = validate_boss_group(legacy_random)
assert migrated["entry"] == "a" and migrated["subgroups"][1]["skills"][0]["next"] == "a"
assert len(migrated["subgroups"][0]["skills"]) == 1
with tempfile.TemporaryDirectory() as folder:
    store = BossStore(Path(folder) / "bosses.json")
    saved = store.save(
        {"name": "RandomBoss", "attributes": {"constitution": 100}, "skillGroup": v}
    )["item"]
    assert store.read()["bosses"][0]["skillGroup"] == saved["skillGroup"] == v
print(
    "PASS: one random position, multi-choice candidate validation, legacy reference migration and save/reload"
)

# Both outcomes share one random position but have independent destinations.
branched = copy.deepcopy(v)
node = branched["subgroups"][0]["skills"][0]
node["skillJumps"] = {old["skills"][0]["id"]: "c", old["skills"][1]["id"]: "a"}
branched = validate_boss_group(branched)
for seed, name, destination in [(1, "Hit", "c"), (0, "Fire", "a")]:
    seq = BossSkillSequence(branched, rng=random.Random(seed))
    assert seq.choose_for_action()["name"] == name
    seq.advance()
    assert seq.current == destination
bad = copy.deepcopy(branched)
bad["subgroups"][0]["skills"][0]["skillJumps"][old["skills"][0]["id"]] = "missing"
try:
    validate_boss_group(bad)
except SkillError:
    pass
else:
    raise AssertionError("invalid candidate jump accepted")
with tempfile.TemporaryDirectory() as folder:
    store = BossStore(Path(folder) / "bosses.json")
    saved = store.save(
        {"name": "BranchBoss", "attributes": {"constitution": 100}, "skillGroup": branched}
    )["item"]
    assert store.read()["bosses"][0]["skillGroup"] == saved["skillGroup"] == branched
print("PASS: each random candidate has its own validated and persisted jump destination")

# Random outcomes retain their own target selection, independent of their jump.
node = branched["subgroups"][0]["skills"][0]
node["skillTargets"] = {old["skills"][0]["id"]: "highestHp", old["skills"][1]["id"]: "lowestArmor"}
branched = validate_boss_group(branched)
for seed, target, destination in [(1, "highestHp", "c"), (0, "lowestArmor", "a")]:
    seq = BossSkillSequence(branched, rng=random.Random(seed))
    assert seq.choose_for_action()["targetSelection"] == target
    seq.advance()
    assert seq.current == destination
assert validate_boss_group(branched) == branched
bad = copy.deepcopy(branched)
bad["subgroups"][0]["skills"][0]["skillTargets"][old["skills"][0]["id"]] = "invalid"
try:
    validate_boss_group(bad)
except SkillError:
    pass
else:
    raise AssertionError("invalid candidate target accepted")
with tempfile.TemporaryDirectory() as folder:
    store = BossStore(Path(folder) / "bosses.json")
    saved = store.save(
        {"name": "TargetsBoss", "attributes": {"constitution": 100}, "skillGroup": branched}
    )["item"]
    assert store.read()["bosses"][0]["skillGroup"] == saved["skillGroup"] == branched
assert migrated["subgroups"][0]["skills"][0]["skillTargets"][old["skills"][0]["id"]] == "random"
print("PASS: per-candidate targets, legacy target migration, validation and persistence")
