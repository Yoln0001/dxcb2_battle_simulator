"""Opt-in Boss combat timeline; ordinary simulations do not instantiate this engine."""

import numpy as np
from .simulation import SingleBattle, add_time
from .compiled.prepare import ATTRS, A
from .compiled.boss import tables, initial_state, periodic, deadline, act, blocked, KINDS
from .health import mark_deaths, reduce_ally_recovery
from .damage import calculate_equipment_damage
from .amplification import attack_snapshot


class BossBattle(SingleBattle):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.boss_attacks = True
        from backend.api.bosses import validate_boss_group

        selected = self.state.target.get("selectedBoss") or {}
        self.boss_group = validate_boss_group(
            selected.get("skillGroup", self.state.target.get("skillGroup"))
        )
        self.boss_tables = tables(args[0], self.state.characters, group=self.boss_group)
        self.boss_runtime = initial_state.py_func(self.boss_tables)
        self.received_rows = []
        proc = []
        ranges = np.zeros((4, 2), np.int64)
        meta = []
        con = []
        for i, c in enumerate(self.state.characters):
            ranges[i, 0] = len(proc)
            if c.enabled:
                for slot in ("weapon", "armor", "accessory1", "accessory2", "stone"):
                    item = self.equipment.get(c.equipment.get(slot))
                    if not item or not item.get("triggerEnabled"):
                        continue
                    for row in item.get("triggerEffects", []):
                        if not row.get("effect"):
                            continue
                        eid = len(meta)
                        matrix = np.zeros((len(ATTRS), len(ATTRS)))
                        for conversion in row["effect"].get("conversions", []):
                            if conversion["enabled"]:
                                for k, v in conversion["coefficients"].items():
                                    matrix[A[conversion["target"]], A[k]] = v
                        meta.append([2 if row["effect"]["kind"] == "amplify" else 0])
                        con.append(matrix)
                        dtype = {
                            "physical": 0,
                            "magic": 1,
                            "none": 2,
                            "receivedPhysical": 10,
                            "receivedMagic": 11,
                        }[row["triggerType"]]
                        proc.append([dtype, row["probability"], eid])
                        self.received_rows.append((item, slot, row))
            ranges[i, 1] = len(proc)
        self.received_data = (
            np.array(proc, dtype=float).reshape((-1, 3)),
            ranges,
            np.array(meta, dtype=float).reshape((-1, 1)),
            np.array(con, dtype=float).reshape((-1, len(ATTRS), len(ATTRS))),
        )
        self.warnings = {
            w
            for w in self.warnings
            if "敌方攻击结算尚未接入" not in w and "敌方受击格挡结算尚未接入" not in w
        }
        if any(
            s.get("effect") and s["effect"].get("type") in ("bleeding", "plague")
            for s in self.boss_group["skills"]
        ):
            self.warnings.add("流血和瘟疫伤害规则尚未指定，暂只记录附加和到期。")

    def arrays(self):
        stats = np.array(
            [[c.stats.get(k, 0) for k in ATTRS] for c in self.state.characters], dtype=float
        )
        hp = np.array([c.current_hp for c in self.state.characters])
        maximum = np.array([c.maximum_hp for c in self.state.characters])
        alive = np.array(
            [int(c.enabled and c.alive) for c in self.state.characters], dtype=np.int64
        )
        return stats, hp, maximum, alive

    def sync(self, stats, hp):
        for i, c in enumerate(self.state.characters):
            c.current_hp = float(hp[i])
            for k, a in A.items():
                if stats[i, a] or k in c.stats:
                    c.stats[k] = float(stats[i, a])
        mark_deaths(self.state)

    def boss_ready(self):
        return self.boss_runtime[1][0] >= 0 and self.state.time >= deadline.py_func(
            self.boss_runtime, self.target_status()
        )

    def boss_periodic(self):
        stats, hp, maximum, alive = self.arrays()
        before_target = self.state.target_current_hp
        damage, healing = periodic.py_func(
            self.state.time, stats, hp, maximum, alive, self.boss_runtime
        )
        self.state.target_current_hp = min(
            self.state.target["hitPoint"], self.state.target_current_hp + healing
        )
        for c, value in enumerate(damage):
            if value:
                self.emit(
                    "boss_dot_damage",
                    target_character=c + 1,
                    damage=float(value),
                    name="Boss持续伤害",
                )
        if healing:
            self.emit(
                "enemy_healing",
                amount=float(healing),
                effective_amount=self.state.target_current_hp - before_target,
                skill_name="Boss回春",
            )
        self.sync(stats, hp)

    def target_status(self):
        value = np.zeros((8, 7))
        keys = {"slow": 3, "stun": 4, "weakness": 5, "fear": 6}
        for debuff in self.boss_debuffs.values():
            if debuff["type"] in keys:
                k = keys[debuff["type"]]
                value[k, 0] = 1
                effect = debuff["effect"]
                source = debuff["source_stats"]
                value[k, 5] = debuff.get(
                    "amount",
                    effect.get("baseValue", 0)
                    + sum(source.get(a, 0) * v for a, v in effect.get("coefficients", {}).items()),
                )
        return value

    def boss_action(self):
        stats, hp, maximum, alive = self.arrays()
        target = np.zeros(20)
        target[0] = self.state.target["hitPoint"]
        target[19] = self.state.target.get("recoveryMultiplier", 1)
        target_debuffs = self.target_status()
        rng = np.array(self.rng.getstate()[1], dtype=np.uint32)
        before_target = self.state.target_current_hp
        released, hits, damage, effects, new_hp, triggers = act.py_func(
            self.state.time,
            self.state.target_current_hp,
            target,
            stats,
            hp,
            maximum,
            alive,
            target_debuffs,
            self.boss_tables,
            self.boss_runtime,
            rng,
            self.received_data,
        )
        self.rng.setstate((3, tuple(int(x) for x in rng), None))
        self.state.target_current_hp = float(new_hp)
        self.sync(stats, hp)
        if released == -2:
            self.emit(
                "boss_wait_started", skill_name="等待", ends_at=float(self.boss_runtime[1][3])
            )
            return
        if released < 0:
            return
        skill = self.boss_group["skills"][released]
        self.emit("boss_skill_released", skill_name=skill["name"], damage_type=skill["damageType"])
        if new_hp > before_target:
            self.emit(
                "enemy_healing" if skill["damageType"] == "none" else "enemy_lifesteal",
                effective_amount=new_hp - before_target,
                skill_name=skill["name"],
            )
        for i in range(4):
            if damage[i]:
                self.emit(
                    "boss_skill_damage",
                    target_character=i + 1,
                    skill_name=skill["name"],
                    damage=float(damage[i]),
                    damage_type=skill["damageType"],
                )
            if effects[i] >= 0:
                self.emit(
                    "boss_debuff_applied",
                    target_character=i + 1,
                    name=KINDS[effects[i]],
                    stacks=int(self.boss_runtime[4][i, effects[i], 0]),
                    expires_at=add_time(self.state.time, skill["effect"]["duration"]),
                )
        for i, hit in enumerate(hits):
            c = self.state.characters[i]
            if not hit or not c.alive:
                continue
            trigger_type = (
                "receivedPhysical" if skill["damageType"] == "physical" else "receivedMagic"
            )
            for item, slot, row in [self.received_rows[triggers[i]]] if triggers[i] >= 0 else []:
                effect = row["effect"]
                kind = effect["kind"]
                name = row["name"] or item["name"]
                self.emit(
                    "equipment_triggered",
                    character=i + 1,
                    equipment_name=item["name"],
                    name=name,
                    kind=kind,
                    equipment_id=item["id"],
                    source_slot=slot,
                    trigger_type=trigger_type,
                )
                snap = attack_snapshot(c, [effect] if kind == "amplify" else [])
                if kind == "buff":
                    self.apply_buff(c, name, effect, item, slot)
                elif kind in ("trueDamage", "physicalTrueDamage", "magicTrueDamage"):
                    dtype = {"physicalTrueDamage": "physical", "magicTrueDamage": "magic"}.get(
                        kind, skill["damageType"]
                    )
                    value = calculate_equipment_damage(snap, effect, self.state.target, dtype)[
                        "final_damage"
                    ]
                    self.deal_damage(value)
                    self.emit(
                        "equipment_damage",
                        character=i + 1,
                        name=name,
                        damage=value,
                        damage_type=dtype,
                    )
                elif kind == "healing":
                    amount = (
                        sum(snap.get(k, 0) * v for k, v in effect["coefficients"].items())
                        * (1 + snap.get("healingBonus", 0) / 100)
                        * (1 + snap.get("finalHealingBonus", 0) / 100)
                    )
                    for recipient in self.recipients(c, effect.get("recipient", "self")):
                        ally = self.state.characters[recipient - 1]
                        if ally.alive:
                            before = ally.current_hp
                            ally.current_hp = min(
                                ally.maximum_hp,
                                before + reduce_ally_recovery(self.state, amount, recipient=ally),
                            )
                            ally.stats["hitPoint"] = ally.current_hp
                            self.emit(
                                "healing",
                                character=i + 1,
                                target_character=recipient,
                                amount=amount,
                                effective_amount=ally.current_hp - before,
                            )
                elif kind == "debuff":
                    self.apply_debuff(c, name, effect, snap, equipment=True)
                elif kind == "immediateAction":
                    self.immediate[i + 1] = add_time(self.state.time, 0.5)

    def action(self, index):
        if not blocked.py_func(index - 1, self.boss_runtime):
            super().action(index)

    def next_event_step(self, step, last_step):
        # Reference path deliberately resolves every grid step, including incoming DOT/expiry.
        return step + 1

    def snapshot(self):
        value = super().snapshot()
        if hasattr(self, "boss_runtime"):
            value["boss_combat_stats"] = {k: float(self.boss_runtime[0][a]) for k, a in A.items()}
            value["boss_combat_stats"]["hitPoint"] = self.state.target_current_hp
            statuses = self.target_status()
            for kind, attribute in ((3, "speed"), (5, "strength"), (6, "technique")):
                if statuses[kind, 0]:
                    value["boss_combat_stats"][attribute] = max(
                        1.0, value["boss_combat_stats"][attribute] - statuses[kind, 5]
                    )
            value["ally_debuffs"] = self.boss_runtime[4].tolist()
        return value
