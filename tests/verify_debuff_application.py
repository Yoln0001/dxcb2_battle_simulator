import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.runtime.debuffs import check_skill_debuff_application as check
from engine.runtime.damage import minimum_damage


class NoRandom:
    def random(self):
        raise AssertionError("miss must not roll debuff chance")


e = {"kind": "debuff", "type": "burn", "applicationRate": 80}
s = {"abnormalBonus": 70}
r = check(s, e, {"resistance": 1000}, hit=True, roll=0.49)
assert r["raw_percent"] == 50 and r["probability"] == 0.5 and r["applied"]
assert not check(s, e, {"resistance": 1000}, hit=True, roll=0.5)["applied"]
assert not check(s, e, {"resistance": 0}, hit=False, rng=NoRandom())["applied"]
assert check(s, e, {"resistance": 0}, hit=True, roll=0.999)["applied"]
assert not check(s, e, {"resistance": 2000}, hit=True, roll=0)["applied"]
assert minimum_damage(0, 100) == 1
print("PASS: hit prerequisite, resistance subtracts chance, 0/100% bounds, universal damage floor")
