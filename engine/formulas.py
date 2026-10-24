"""原有伤害公式，保留全部计算系数。"""
from numba import njit

@njit
def simulate_damage_berserker(attack_strength, weaponPower, loopDamage, lootPhysicalDamage,
                              lootCriticalStrikeDamageCoefficient):
    hit_damage = ((attack_strength * 9.5 + weaponPower) * (1.62 + lootCriticalStrikeDamageCoefficient) *
                  (1 + loopDamage + lootPhysicalDamage) * 1.04 * 1.1) * 1.3
    # print(f"攻击伤害: {hit_damage:.0f}")
    damage = hit_damage
    return damage


@njit
def simulate_damage_holy_lancer_1(attack_strength, attack_technique, weaponPower, loopDamage,
                                  lootPhysicalDamage, lootCriticalStrikeDamageCoefficient):
    hit_damage = ((attack_strength * 1.5 + attack_technique * 0.95 + weaponPower) * (
            1.5 + 0.5 + lootCriticalStrikeDamageCoefficient) *
                  (1 + loopDamage + lootPhysicalDamage) * 1.01 * 1.1) * 3
    return hit_damage


@njit
def simulate_damage_holy_lancer_2(attack_strength, attack_technique, weaponPower, loopDamage,
                                  lootPhysicalDamage, lootCriticalStrikeDamageCoefficient):
    hit_damage = ((attack_strength * 2.75 + attack_technique * 1.25 + weaponPower) * (
            1.5 + 0.06 + lootCriticalStrikeDamageCoefficient) *
                  (1 + loopDamage + lootPhysicalDamage) * 1.01 * 1.1) * 3
    return hit_damage


@njit
def simulate_damage_nightmare(attack_strength, attack_speed, weapon_power,
                              loot_critical_strike_damage_coefficient, loop_damage, loot_physical_damage):
    damage = ((attack_strength * 0.95 + attack_speed * 0.05 + weapon_power) *
              (1.5 + 0.06 + loot_critical_strike_damage_coefficient) *
              (1 + loop_damage + loot_physical_damage) * 1.04 * 1.1)
    return damage


