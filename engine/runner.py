"""直接运行本文件，打印与原脚本相同的全部统计项目。"""
import argparse
import time
import numpy as np
from .models import CharacterConfig, Berserker, Holy_lancer_1, Holy_lancer_2, Nightmare
from .battle import Battle

def find_percentile(data, value):
    data_sorted = np.sort(data)
    n = len(data_sorted)
    # 计算小于等于 value 的数据比例
    count = np.sum(data_sorted <= value)
    percentile = (count / n) * 100
    return percentile


if __name__ == "__main__":
    start_time = time.time()

    # 定义各角色参数
    # 我的配置
    # 狂战神
    berserker_config = CharacterConfig(
        strength=11426,
        magic=0,
        technique=2748,
        speed=2614,
        hitPoint=44790,
        weaponPower=1065,
        loopDamage=0.26,
        lootMagicDamage=0,
        lootPhysicalDamage=0,
        lootHitRate=0.1 + 0.012,
        lootCriticalStrikeDamageCoefficient=0)
    # 圣枪1
    holy_lancer_1_config = CharacterConfig(
        strength=3740,
        magic=0,
        technique=10253,
        speed=2579,
        hitPoint=0,
        weaponPower=631,
        loopDamage=0.248,
        lootMagicDamage=0,
        lootPhysicalDamage=0,
        lootHitRate=0,
        lootCriticalStrikeDamageCoefficient=0)
    # 圣枪2
    holy_lancer_2_config = CharacterConfig(
        strength=6796,
        magic=0,
        technique=6458,
        speed=3293,
        hitPoint=0,
        weaponPower=740,
        loopDamage=0.26,
        lootMagicDamage=0,
        lootPhysicalDamage=0,
        lootHitRate=0.033,
        lootCriticalStrikeDamageCoefficient=0.177)
    # 夜魇
    nightmare_config = CharacterConfig(
        strength=3093,
        magic=0,
        technique=0,
        speed=10021,
        hitPoint=0,
        weaponPower=693,
        loopDamage=0.248,
        lootMagicDamage=0,
        lootPhysicalDamage=0,
        lootHitRate=0.015 + 0.015,
        lootCriticalStrikeDamageCoefficient=0.06 + 0.075)

    # 实际伤害
    real_damage = 168888399

    # 创建角色对象（注意：每个角色用对应的子类实例化）
    berserker = Berserker(berserker_config, holy_lancer_1_config.technique)
    holy_lancer_1 = Holy_lancer_1(holy_lancer_1_config, holy_lancer_1_config.technique)
    holy_lancer_2 = Holy_lancer_2(holy_lancer_2_config, holy_lancer_1_config.technique)
    nightmare = Nightmare(nightmare_config)

    battle = Battle([berserker, holy_lancer_1, holy_lancer_2, nightmare])
    # battle = Battle([holy_lancer_1])

    parser = argparse.ArgumentParser(description="人形魂碑战力测试")
    parser.add_argument("--simulations", type=int, default=100_0000,
                        help="模拟次数，默认与原脚本一致：1000000")
    args = parser.parse_args()
    if args.simulations < 1:
        parser.error("模拟次数必须大于0")
    simulations = args.simulations
    # simulations = 1

    damage_results = battle.simulate(simulations)

    # 统计数据计算
    mean_damage = np.mean(damage_results)
    max_damage = np.max(damage_results)
    min_damage = np.min(damage_results)
    variance_damage = np.var(damage_results)

    # 分位数计算
    percentile_1 = np.percentile(damage_results, 1)
    percentile_5 = np.percentile(damage_results, 5)
    percentile_10 = np.percentile(damage_results, 10)
    percentile_15 = np.percentile(damage_results, 15)
    percentile_20 = np.percentile(damage_results, 20)
    percentile_25 = np.percentile(damage_results, 25)
    percentile_30 = np.percentile(damage_results, 30)
    percentile_35 = np.percentile(damage_results, 35)
    percentile_40 = np.percentile(damage_results, 40)
    percentile_45 = np.percentile(damage_results, 45)
    percentile_50 = np.percentile(damage_results, 50)
    percentile_55 = np.percentile(damage_results, 55)
    percentile_60 = np.percentile(damage_results, 60)
    percentile_65 = np.percentile(damage_results, 65)
    percentile_70 = np.percentile(damage_results, 70)
    percentile_75 = np.percentile(damage_results, 75)
    percentile_80 = np.percentile(damage_results, 80)
    percentile_85 = np.percentile(damage_results, 85)
    percentile_90 = np.percentile(damage_results, 90)
    percentile_95 = np.percentile(damage_results, 95)
    percentile_97 = np.percentile(damage_results, 97)
    percentile_975 = np.percentile(damage_results, 97.5)
    percentile_98 = np.percentile(damage_results, 98)
    percentile_99 = np.percentile(damage_results, 99)
    percentile_993 = np.percentile(damage_results, 99.3)
    percentile_995 = np.percentile(damage_results, 99.5)
    percentile_997 = np.percentile(damage_results, 99.7)
    percentile_999 = np.percentile(damage_results, 99.9)
    percentile_9993 = np.percentile(damage_results, 99.93)

    print(f"Mean Damage: {mean_damage}")
    print(f"Min Damage: {min_damage}")
    print(f"Variance of Damage: {variance_damage}")
    print(f"1th Percentile: {percentile_1}")
    print(f"5th Percentile: {percentile_5}")
    print(f"10th Percentile: {percentile_10}")
    print(f"15th Percentile: {percentile_15}")
    print(f"20th Percentile: {percentile_20}")
    print(f"25th Percentile: {percentile_25}")
    print(f"30th Percentile: {percentile_30}")
    print(f"35th Percentile: {percentile_35}")
    print(f"40th Percentile: {percentile_40}")
    print(f"45th Percentile: {percentile_45}")
    print(f"50th Percentile: {percentile_50}")
    print(f"55th Percentile: {percentile_55}")
    print(f"60th Percentile: {percentile_60}")
    print(f"65th Percentile: {percentile_65}")
    print(f"70th Percentile: {percentile_70}")
    print(f"75th Percentile: {percentile_75}")
    print(f"80th Percentile: {percentile_80}")
    print(f"85th Percentile: {percentile_85}")
    print(f"90th Percentile: {percentile_90}")
    print(f"95th Percentile: {percentile_95}")
    print(f"97th Percentile: {percentile_97}")
    print(f"97.5th Percentile: {percentile_975}")
    print(f"98th Percentile: {percentile_98}")
    print(f"99th Percentile: {percentile_99}")
    print(f"99.3th Percentile: {percentile_993}")
    print(f"99.5th Percentile: {percentile_995}")
    print(f"99.7th Percentile: {percentile_997}")
    print(f"99.9th Percentile: {percentile_999}")
    print(f"99.93th Percentile: {percentile_9993}")
    print(f"Max Damage: {max_damage}")

    percentile = find_percentile(damage_results, real_damage)
    print(f"{real_damage} 对应的分位数是 {percentile}%")

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"程序运行时间: {elapsed_time} 秒")


