"""Opt-in performance benchmark, using in-memory fixtures only."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.runtime.batch import simulate_batch

def main():
    stats={'constitution':3000,'magic':15000,'technique':6000,'strength':500,'speed':1500,'hitRate':60}
    config={'seed':123,'battle':{'duration':200,'simulations':10},'target':{'hitPoint':175000000,'speed':43750,'magicVulnerability':1.12},'characters':[{'job':'法师','enabled':True,'stats':stats.copy(),'equipment':{},'skillGroup':'g'} for _ in range(4)]}
    config['characters'][0].update(contract='旧日支配者-魔',negativeEffect='群体献祭',skillMultiplier=5.6)
    skills={'fire':{'name':'炎爆术Lv.8','job':'法师','damageType':'magic','cooldown':1.8,'hitRate':45,'criticalRate':37,'coefficients':{'magic':4.4},'effect':{'kind':'debuff','type':'burn','duration':6,'applicationRate':70,'baseValue':1,'coefficients':{'technique':.25}}},'heal':{'name':'静气凝神Lv.7','job':'法师','damageType':'none','cooldown':3,'coefficients':{'magic':.6},'effect':{'kind':'buff','type':'technique','duration':15,'triggerRate':100,'recipient':'allAllies','baseValue':5,'conversions':[{'target':'technique','enabled':True,'coefficients':{'technique':.25}}]}}}
    groups={'g':{'job':'法师','entry':'a','subgroups':[{'id':'sub','nextGroup':'sub','skills':[{'id':'a','skillId':'heal','next':''},{'id':'b','skillId':'fire','next':''}]}]}}
    result=simulate_batch(config,{},skills,groups,parallel=False)
    print('10 runs new serial:',round(result['elapsed_seconds'],3),'seconds',flush=True)
    config['battle']['simulations']=1000
    serial=simulate_batch(config,{},skills,groups,parallel=False)
    parallel=simulate_batch(config,{},skills,groups)
    for key in ['passed_battles','sorted_damage','characters','expected_damage']:assert serial[key]==parallel[key]
    print('1000 runs serial:',round(serial['elapsed_seconds'],3),'parallel:',round(parallel['elapsed_seconds'],3),'workers:',parallel['worker_count'],flush=True)
    config['battle']['simulations']=10000
    result=simulate_batch(config,{},skills,groups)
    print('10000 runs:',round(result['elapsed_seconds'],3),'seconds; pass rate:',result['pass_rate'],flush=True)

if __name__=='__main__':main()
