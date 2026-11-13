"""角色面板及角色接口；队友技巧通过参数传入，不再依赖全局配置。"""

from dataclasses import dataclass
from abc import ABC
from .battle import (
    simulate_attack_berserker,
    simulate_attack_holy_lancer_1,
    simulate_attack_holy_lancer_2,
    simulate_attack_nightmare,
)


@dataclass
class CharacterConfig:
    # 角色共有属性
    strength: float = 0
    magic: float = 0
    technique: float = 0
    speed: float = 0
    hitPoint: float = 0
    weaponPower: float = 0
    loopDamage: float = 0

    lootMagicDamage: float = 0
    lootPhysicalDamage: float = 0
    lootHitRate: float = 0
    lootCriticalStrikeDamageCoefficient: float = 0


class Character(ABC):
    def __init__(self, config: CharacterConfig, holy_lancer_1_tech_value: float = 0):
        self.config = config
        self.holy_lancer_1_tech_value = holy_lancer_1_tech_value

    def simulate_attack(self) -> float:
        """抽象接口，具体子类实现调用加速函数"""
        pass


class Berserker(Character):
    def simulate_attack(self) -> float:
        return simulate_attack_berserker(
            self.config.strength,
            self.config.magic,
            self.config.technique,
            self.config.speed,
            self.config.hitPoint,
            self.config.weaponPower,
            self.config.loopDamage,
            self.config.lootMagicDamage,
            self.config.lootPhysicalDamage,
            self.config.lootHitRate,
            self.config.lootCriticalStrikeDamageCoefficient,
            self.holy_lancer_1_tech_value,
        )


class Holy_lancer_1(Character):
    def simulate_attack(self) -> float:
        return simulate_attack_holy_lancer_1(
            self.config.strength,
            self.config.magic,
            self.config.technique,
            self.config.speed,
            self.config.hitPoint,
            self.config.weaponPower,
            self.config.loopDamage,
            self.config.lootMagicDamage,
            self.config.lootPhysicalDamage,
            self.config.lootHitRate,
            self.config.lootCriticalStrikeDamageCoefficient,
            self.holy_lancer_1_tech_value,
        )


class Holy_lancer_2(Character):
    def simulate_attack(self) -> float:
        return simulate_attack_holy_lancer_2(
            self.config.strength,
            self.config.magic,
            self.config.technique,
            self.config.speed,
            self.config.hitPoint,
            self.config.weaponPower,
            self.config.loopDamage,
            self.config.lootMagicDamage,
            self.config.lootPhysicalDamage,
            self.config.lootHitRate,
            self.config.lootCriticalStrikeDamageCoefficient,
            self.holy_lancer_1_tech_value,
        )


class Nightmare(Character):
    def simulate_attack(self) -> float:
        return simulate_attack_nightmare(
            self.config.speed,
            self.config.strength,
            self.config.weaponPower,
            self.config.lootCriticalStrikeDamageCoefficient,
            self.config.loopDamage,
            self.config.lootPhysicalDamage,
        )
