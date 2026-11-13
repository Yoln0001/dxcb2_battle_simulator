"""Boss subgroup decisions and unconditional transitions, independent of equipment."""

from copy import deepcopy
import random
from .initialization import BattleConfigurationError


class BossSkillSequence:
    def __init__(self, group, *, rng=None):
        self.group = deepcopy(group)
        self.rng = rng or random.Random()
        self.skills = {s["id"]: s for s in self.group["skills"]}
        self.subgroups = {s["id"]: s for s in self.group["subgroups"]}
        self.nodes = {n["id"]: (s, n) for s in self.group["subgroups"] for n in s["skills"]}
        self.current = self.group["entry"]
        self.selected = None
        self.selected_skill_id = None

    def choose_for_action(self, characters=(), *, boss_hp=0, boss_max_hp=0, time=0):
        if not self.current:
            return None
        sub, node = self.nodes[self.current]
        mode = sub.get("type", "sequential")
        if mode == "random":
            node = sub["skills"][0]
        elif mode == "conditional":
            for candidate in sub["skills"]:
                condition = candidate["releaseCondition"]
                kind = condition["kind"]
                threshold = condition.get("threshold", 0)
                low = any(
                    c.enabled
                    and c.alive
                    and c.maximum_hp > 0
                    and c.current_hp / c.maximum_hp * 100 < threshold
                    for c in characters
                )
                percent = boss_hp / boss_max_hp * 100 if boss_max_hp > 0 else 100
                matched = (
                    kind == "always"
                    or kind == "bossHealthBelow"
                    and percent < threshold
                    or kind == "bossHealthAbove"
                    and percent > threshold
                    or kind == "enemyHealthBelow"
                    and low
                    or kind == "noEnemyHealthBelow"
                    and not low
                    or kind == "timeAtLeast"
                    and time >= threshold
                )
                if matched:
                    node = candidate
                    break
            else:
                raise BattleConfigurationError("Boss条件组缺少else分支")
        self.selected = node
        self.current = node["id"]
        skill_id = (
            (
                self.rng.choice(node["skillIds"])
                if len(node["skillIds"]) > 1
                else node["skillIds"][0]
            )
            if mode == "random"
            else node["skillId"]
        )
        self.selected_skill_id = skill_id
        skill = (
            {"name": "等待", "damageType": "wait", "waitDuration": node.get("waitDuration", 1)}
            if skill_id == "__wait__"
            else deepcopy(self.skills[skill_id])
        )
        skill["targetSelection"] = (
            node.get("skillTargets", {}).get(skill_id, "lowestHp")
            if mode == "random"
            else node.get("targetSelection", "lowestHp")
        )
        return skill

    def advance(self):
        if not self.current:
            return
        sub, node = self.nodes[self.current]
        following = ""
        if sub.get("type", "sequential") == "sequential":
            index = sub["skills"].index(node)
            if index + 1 < len(sub["skills"]):
                following = sub["skills"][index + 1]["id"]
        if not following and sub.get("nextGroup"):
            following = self.subgroups[sub["nextGroup"]]["skills"][0]["id"]
        jump = (
            node.get("skillJumps", {}).get(self.selected_skill_id, "")
            if sub.get("type") == "random"
            else node.get("next", "")
        )
        self.current = jump or following
        self.selected = None
        self.selected_skill_id = None
