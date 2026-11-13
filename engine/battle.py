"""原有整场攻击循环和多次模拟；本次拆分不改变时间及结算规则。"""

import math
import numpy as np
from numba import njit
from .formulas import (
    simulate_damage_berserker,
    simulate_damage_holy_lancer_1,
    simulate_damage_holy_lancer_2,
    simulate_damage_nightmare,
)
from .effects import (
    berserker_start_strength,
    holy_lancer_team_technique,
    berserker_attack_effect,
)


@njit
def simulate_attack_berserker(
    strength,
    magic,
    technique,
    speed,
    hitPoint,
    weaponPower,
    loopDamage,
    lootMagicDamage,
    lootPhysicalDamage,
    lootHitRate,
    lootCriticalStrikeDamageCoefficient,
    holy_lancer_1_tech_value: float,
):
    strength = berserker_start_strength(strength)
    technique = holy_lancer_team_technique(technique, holy_lancer_1_tech_value)
    total_damage = 0.0
    battle_time = 4.5
    while battle_time <= 200:
        attack_strength, attack_technique, cool_down = berserker_attack_effect(
            strength, technique, hitPoint
        )
        battle_time += cool_down
        hit_rate = (
            30 + 0 + 5 + 10 + 20 + 15 + lootHitRate * 100 + 2 + attack_technique / 4375 * 3
        ) / 100.0
        if np.random.random() < hit_rate:
            damage = simulate_damage_berserker(
                attack_strength,
                weaponPower,
                loopDamage,
                lootPhysicalDamage,
                lootCriticalStrikeDamageCoefficient,
            )
        else:
            damage = 0
        total_damage += damage
        # print(f"伤害: {damage:.0f}    战斗时间: {battle_time}")
    return total_damage


@njit
def simulate_attack_holy_lancer_1(
    strength,
    magic,
    technique,
    speed,
    hitPoint,
    weaponPower,
    loopDamage,
    lootMagicDamage,
    lootPhysicalDamage,
    lootHitRate,
    lootCriticalStrikeDamageCoefficient,
    holy_lancer_1_tech_value: float,
):
    technique = holy_lancer_team_technique(technique, holy_lancer_1_tech_value)
    technique *= 1.35
    total_damage = 0.0
    battle_time = 1.5
    buff_time_left = 0
    while battle_time <= 200:
        cool_down = 2.5
        if buff_time_left > 0:
            buffed_technique = technique * 1.5
        else:
            buffed_technique = technique

        if np.random.random() < 0.5:
            buff_time_left = 8
            attack_strength = strength
            attack_technique = buffed_technique
            buff_time_left -= cool_down
        else:
            attack_strength = strength * 2
            attack_technique = buffed_technique * 2.5
            buff_time_left -= cool_down

        damage = simulate_damage_holy_lancer_1(
            attack_strength,
            attack_technique,
            weaponPower,
            loopDamage,
            lootPhysicalDamage,
            lootCriticalStrikeDamageCoefficient,
        )

        battle_time += cool_down
        total_damage += damage
        # print(f"伤害: {damage:.0f}    战斗时间: {battle_time} 专注剩余层数: {buff_time_left}")
    return total_damage


@njit
def simulate_attack_holy_lancer_2(
    strength,
    magic,
    technique,
    speed,
    hitPoint,
    weaponPower,
    loopDamage,
    lootMagicDamage,
    lootPhysicalDamage,
    lootHitRate,
    lootCriticalStrikeDamageCoefficient,
    holy_lancer_1_tech_value: float,
):
    technique = holy_lancer_team_technique(technique, holy_lancer_1_tech_value)
    total_damage = 0.0
    battle_time = 1.5
    while battle_time <= 200:
        cool_down = 2.5
        if np.random.random() < 0.8:
            attack_strength = strength * 2.1 + technique * 0.7
            attack_technique = technique
        elif np.random.random() < 0.1:
            attack_strength = strength * 1.8 + technique * 2
            attack_technique = technique
        else:
            attack_strength = strength + technique * 0.65
            attack_technique = technique

        damage = simulate_damage_holy_lancer_2(
            attack_strength,
            attack_technique,
            weaponPower,
            loopDamage,
            lootPhysicalDamage,
            lootCriticalStrikeDamageCoefficient,
        )

        battle_time += cool_down
        total_damage += damage
        # print(f"伤害: {damage:.0f}    战斗时间: {battle_time}")
    return total_damage


@njit
def simulate_attack_nightmare(
    speed,
    strength,
    weapon_power,
    loot_critical_strike_damage_coefficient,
    loop_damage,
    loot_physical_damage,
):
    # 神兽之怒加力量
    strength = strength * 1.65
    total_damage = 0.0
    buff_time_left = 0.0
    buff_level = 0
    battle_time = math.floor((strength - 300) / (speed + 1) * 10) / 10.0 + 1.5
    while battle_time <= 200:
        buff_speed = speed * (1 + 0.3 * buff_level)
        strength_speed_ratio = math.floor((strength - 300) / (buff_speed + 1) * 10) / 10.0
        cool_down = max(strength_speed_ratio + 1.5 - 1.2, 0.5)
        battle_time += cool_down
        if np.random.random() < 0.1:
            attack_strength = strength
            attack_speed = buff_speed
            buff_time_left = 10.0 - cool_down
            if buff_level < 5:
                buff_level += 1
        else:
            attack_strength = buff_speed * 1.3 + strength * 1.5
            attack_speed = buff_speed
            if buff_time_left >= 0:
                buff_time_left -= cool_down
            if buff_time_left < 0:
                buff_level = 0
        damage = simulate_damage_nightmare(
            attack_strength,
            attack_speed,
            weapon_power,
            loot_critical_strike_damage_coefficient,
            loop_damage,
            loot_physical_damage,
        )
        total_damage += damage
        # print(f"伤害: {damage:.0f}    黑暗之舞层数: {buff_level}    "
        #       f"黑暗之舞剩余次数: {buff_time_left}  力速比: {strength_speed_ratio}  战斗时间: {battle_time}")
    return total_damage + 17500000


class Battle:
    def __init__(self, characters: list):
        self.characters = characters

    def simulate(self, simulations: int) -> list:
        damage_results = [
            sum(character.simulate_attack() for character in self.characters)
            for _ in range(simulations)
        ]
        return damage_results
