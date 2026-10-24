from pathlib import Path
import sys,copy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from engine.runtime.batch import simulate_batch,percentile
from engine.runtime.simulation import SingleBattle
cfg={'seed':123,'battle':{'duration':3,'simulations':10},'target':{'speed':100,'hitPoint':300,'magicVulnerability':1},'characters':[{'job':'寒霜法师','enabled':i==0,'stats':{'constitution':100,'magic':100,'strength':0,'speed':99,'hitRate':100},'equipment':{'accessory1':'item'} if i==0 else {},'skillGroup':'g'} for i in range(4)]}
skill={'name':'攻击','job':'寒霜法师','damageType':'magic','cooldown':0,'hitRate':0,'coefficients':{'magic':1},'effect':None}
group={'job':'寒霜法师','entry':'n','subgroups':[{'id':'sub','nextGroup':'sub','skills':[{'id':'n','skillId':'s','next':''}]}]}
item={'id':'item','name':'装备','category':'accessory','startingBuff':{'enabled':False},'triggerEnabled':True,'triggerEffects':[{'name':'额外真伤','triggerType':'magic','probability':100,'effect':{'kind':'magicTrueDamage','coefficients':{'magic':1}}}]}
equipment={'item':item};skills={'s':skill};groups={'g':group}
progress=[]
r=simulate_batch(cfg,equipment,skills,groups,progress=lambda done,total:progress.append((done,total)))
assert r['total_battles']==10 and r['passed_battles']==10 and r['pass_rate']==100
assert r['expected_damage']==400 and r['min_damage']==400 and r['max_damage']==400
assert r['percentiles']=={'1':400,'5':400,'10':400}
assert r['characters'][0]['expected_damage']==400
assert r['characters'][0]['effects'][0]['mean_count']==2
assert all(c['expected_damage']==0 for c in r['characters'][1:])
assert progress[-1]==(10,10) and r['elapsed_seconds']>=0
assert percentile([0,100],1)==99 and percentile([0,100],5)==95 and percentile([0,100],10)==90
assert percentile([0,100],0)==100 and percentile([0,100],100)==0
seed=999
single=SingleBattle(cfg,equipment,skills,groups,seed=seed).run();compact=SingleBattle(cfg,equipment,skills,groups,seed=seed,record_timeline=False).run()
for key in ['total_damage','end_reason','character_damage','effect_counts']:assert single[key]==compact[key]
assert compact['timeline']==[] and compact['final_state'] is None
cfg['target']['hitPoint']=500
assert simulate_batch(cfg,equipment,skills,groups)['passed_battles']==0
item['triggerEffects'][0]['probability']=0
r=simulate_batch(cfg,equipment,skills,groups)
assert r['characters'][0]['effects'][0]['mean_count']==0
assert sum(c['expected_damage'] for c in r['characters'])==r['expected_damage']
print('PASS: count/pass rate, mean/extrema/linear quantiles, per-character totals, zero-inclusive proc means, elapsed and engine equivalence')
