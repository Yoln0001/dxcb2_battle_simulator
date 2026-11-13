"""Interactive 0.1 second combat with deterministic operation-log rewind."""

from copy import deepcopy
from .boss_simulation import BossBattle
from .simulation import SkillSequence, SingleBattle
from .cooldowns import action_ready_now, check_action_ready
from .compiled.boss import blocked
from .initialization import BattleConfigurationError


class TasBattle(BossBattle):
    def __init__(self, config, equipment, skills, groups, *, seed):
        config, groups = deepcopy(config), deepcopy(groups)
        self.automatic_groups = set()
        for index, row in enumerate(config.get("characters", []), 1):
            if not row.get("enabled", True):
                continue
            if groups.get(row.get("skillGroup")):
                self.automatic_groups.add(index)
            else:
                key = "__tas_manual_" + str(index)
                row["skillGroup"] = key
                groups[key] = {
                    "job": row["job"],
                    "entry": "manual",
                    "subgroups": [
                        {
                            "id": "manual",
                            "skills": [
                                {
                                    "id": "manual",
                                    "skillId": "__wait__",
                                    "waitDuration": 0.1,
                                    "next": "",
                                }
                            ],
                        }
                    ],
                }
        selected = config.get("target", {}).get("selectedBoss") or {}
        boss_group = selected.get("skillGroup") or config.get("target", {}).get("skillGroup") or {}
        if boss_group.get("entry") and boss_group.get("subgroups"):
            super().__init__(config, equipment, skills, groups, seed=seed)
        else:
            SingleBattle.__init__(self, config, equipment, skills, groups, seed=seed)
        self.skills = skills
        self.modes = ["manual"] * 4
        self.selection = None
        self.pending = None
        if not self.boss_attacks:
            self.warnings.add("当前 Boss 未设置技能组，TAS 本场不执行 Boss 攻击。")

    def has_manual_action(self, index):
        return self.modes[index - 1] == "manual"

    def before_action(self, index):
        c = self.state.characters[index - 1]
        if self.modes[index - 1] != "manual" or not c.enabled or not c.alive:
            return
        if self.boss_attacks and blocked.py_func(index - 1, self.boss_runtime):
            return
        if index in self.waiting:
            if self.state.time < self.waiting[index]:
                return
            self.waiting.pop(index)
            self.sequences[index].advance()
            self.emit("wait_finished", character=index)
        forced = self.immediate.get(index)
        if not (
            self.state.time >= forced
            if forced is not None
            else action_ready_now(c, self.state.time)
        ):
            return
        self.pending = index
        yield {"kind": "decision", "character": index}
        self.pending = None

    def healing_target(self, source):
        target = self.selection.get("target_character") if self.selection else None
        return self.state.characters[target - 1] if target else super().healing_target(source)

    def action(self, index):
        if self.selection and self.selection["character"] == index:
            if self.selection["kind"] == "hold":
                self.emit("tas_hold", character=index, duration=0.1)
                self.selection = None
                return
            skill = deepcopy(self.skills[self.selection["skill_id"]])
            skill["targetSelection"] = self.selection.get("target_selection", "default")
            original = self.sequences[index]
            group = {
                "job": original.group["job"],
                "entry": "tas",
                "subgroups": [
                    {"id": "tas", "skills": [{"id": "tas", "skillId": "tas", "next": ""}]}
                ],
            }
            self.sequences[index] = SkillSequence(group, {"tas": skill}, original.group["job"])
            # SkillSequence normally supplies its node's targeting preference.
            self.sequences[index].nodes["tas"]["targetSelection"] = skill["targetSelection"]
            try:
                SingleBattle.action(self, index)
            finally:
                self.sequences[index] = original
                self.selection = None
        elif self.boss_attacks:
            super().action(index)
        else:
            SingleBattle.action(self, index)


class TasSession:
    def __init__(self, config, equipment, skills, groups):
        self.args = deepcopy((config, equipment, skills, groups))
        self.seed = config.get("seed")
        self.log = []
        self.cursor = 0
        self.revision = 0
        self.reset()
        self.seed = self.battle.seed

    def reset(self):
        self.battle = TasBattle(*self.args, seed=self.seed)
        self.iterator = self.battle.iter_run()
        self.signal = next(self.iterator)
        self.done = False
        self.result = None

    def consume(self):
        try:
            self.signal = next(self.iterator)
        except StopIteration as finished:
            self.done = True
            self.result = finished.value
            self.signal = {"kind": "finished"}

    def apply(self, operation):
        kind = operation.get("kind")
        if kind == "step":
            if self.done:
                return
            if self.battle.pending:
                raise BattleConfigurationError("请先选择待行动角色的技能，或将该角色切换为自动")
            self.consume()
        elif kind in ("cast", "hold"):
            index = operation.get("character")
            skill_id = operation.get("skill_id")
            if type(index) is not int or self.battle.pending != index or self.done:
                raise BattleConfigurationError("该角色尚未轮到行动，或冷却尚未结束")
            skill = self.battle.skills.get(skill_id)
            c = self.battle.state.characters[index - 1]
            if kind == "cast" and (
                not skill
                or skill.get("job") != c.job
                or skill.get("damageType") not in ("physical", "magic", "none")
            ):
                raise BattleConfigurationError("请选择当前角色转职的有效技能")
            target = operation.get("target_character")
            if (
                target is not None
                and kind == "cast"
                and (
                    skill["damageType"] != "none"
                    or skill.get("healingRecipient", "self") == "allAllies"
                )
            ):
                raise BattleConfigurationError(
                    "只有单体回复技能可以指定队友，群体回复会作用于全体存活队友"
                )
            if target is not None and (
                type(target) is not int
                or not 1 <= target <= 4
                or not self.battle.state.characters[target - 1].enabled
                or not self.battle.state.characters[target - 1].alive
            ):
                raise BattleConfigurationError("回复对象必须是存活的参战角色")
            self.battle.selection = deepcopy(operation)
            self.consume()
        elif kind == "mode":
            index = operation.get("character")
            mode = operation.get("mode")
            if type(index) is not int or not 1 <= index <= 4 or mode not in ("auto", "manual"):
                raise BattleConfigurationError("角色模式无效")
            if mode == "auto" and index not in self.battle.automatic_groups:
                raise BattleConfigurationError("该角色未配置技能组，请使用手动模式或先选择技能组")
            self.battle.modes[index - 1] = mode
            if mode == "auto" and self.battle.pending == index:
                self.consume()
        else:
            raise BattleConfigurationError("TAS 操作无效")

    def operate(self, operation):
        # Record only successful mutations; exploring after rewind creates a branch.
        self.apply(operation)
        self.log[self.cursor :] = [{**deepcopy(operation), "time": self.battle.state.time}]
        self.cursor += 1
        self.revision += 1
        return self.view()

    def seek(self, tick):
        if type(tick) is not int or not 0 <= tick <= round(self.horizon() * 10):
            raise BattleConfigurationError("只能回溯到已探索的时间轴，时间精度为0.1秒")
        self.reset()
        self.cursor = 0
        for operation in self.log:
            if round(operation["time"] * 10) > tick:
                break
            self.apply(operation)
            self.cursor += 1
        self.revision += 1
        return self.view()

    def horizon(self):
        return max([0] + [op["time"] for op in self.log])

    def view(self):
        b = self.battle
        characters = []
        for c in b.state.characters:
            readiness = check_action_ready(c, b.state.time)
            statuses = []
            if b.boss_attacks:
                from .compiled.boss import KINDS

                statuses = [
                    {
                        "type": kind,
                        "stacks": int(row[0]),
                        "expires_at": float(row[1]),
                        "amount": float(row[3]),
                    }
                    for kind, row in zip(KINDS, b.boss_runtime[4][c.index - 1])
                    if row[0] > 0
                ]
            characters.append(
                {
                    "index": c.index,
                    "mode": b.modes[c.index - 1],
                    "ready": readiness["ready"],
                    "next_action_at": readiness["next_action_at"],
                    "statuses": statuses,
                    "automatic_available": c.index in b.automatic_groups,
                    "skills": [
                        {
                            "id": sid,
                            "name": s["name"],
                            "damage_type": s["damageType"],
                            "healing_recipient": s.get("healingRecipient", "self"),
                            "cooldown": s["cooldown"],
                        }
                        for sid, s in b.skills.items()
                        if s.get("job") == c.job
                        and s.get("damageType") in ("physical", "magic", "none")
                    ],
                }
            )
        # A decision may be part way through a tick: expose the live state and events.
        now = b.state.time
        return {
            "seed": self.seed,
            "revision": self.revision,
            "time": now,
            "step": 0.1,
            "duration": b.duration,
            "horizon": self.horizon(),
            "finished": self.done,
            "end_reason": b.end_reason if self.done else None,
            "pending_character": b.pending,
            "boss_attacks": b.boss_attacks,
            "target_maximum_hp": b.state.target["hitPoint"],
            "total_damage": b.total_damage,
            "snapshot": b.snapshot(),
            "characters": characters,
            "events": deepcopy([e for e in b.state.events if e["time"] == now]),
            "warnings": sorted(b.warnings),
            "decisions": [
                {
                    "time": op["time"],
                    "character": op["character"],
                    "skill_id": op.get("skill_id", "__hold__"),
                }
                for op in self.log[: self.cursor]
                if op["kind"] in ("cast", "hold")
            ],
        }
