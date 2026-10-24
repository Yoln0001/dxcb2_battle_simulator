"""Compare warm njit modes on the same read-only saved equipment/skill fixture."""
import ast,copy,json,statistics
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.api.bosses import validate_boss_group
from backend.equipment.jobs import JOB_FAMILIES
from engine.runtime.batch import simulate_batch


def main():
    path=Path(__file__).with_name('benchmark_compiled_batch.py')
    tree=ast.parse(path.read_text(encoding='utf-8'));function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main');body=[]
    for statement in function.body:
        if isinstance(statement,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='reference' for t in statement.targets):break
        body.append(statement)
    ns={'__file__':str(path),'Path':Path,'json':json};exec(compile(ast.Module(body=body,type_ignores=[]),'saved_fixture','exec'),ns)
    cfg,eq,sl,gl=[ns[k] for k in ('config','eq','sl','gl')]
    for row in cfg['characters']:
        used=set()
        for slot,old in row['equipment'].items():
            category='accessory' if slot.startswith('accessory') else slot
            choices=[e for e in eq.values() if e['id'] not in used and e['category']==category and (slot!='weapon' or not e.get('weaponJob') or e['weaponJob']==JOB_FAMILIES[row['job']])]
            row['equipment'][slot]=old if any(e['id']==old for e in choices) else choices[0]['id'] if choices else ''
            used.add(row['equipment'][slot])
    cfg['target']['selectedBoss']={'attributes':{'strength':100,'speed':10000,'technique':0},'skillGroup':validate_boss_group({'skills':[{'id':'hit','name':'测速用群体物理攻击','damageType':'physical','targeting':'all','cooldown':0,'baseValue':1,'coefficients':{},'hitRate':100,'effect':None}]})}
    # Low damage keeps battle length comparable; both modes use the same configuration/seed.
    cfg['battle']['simulations']=1
    for enabled in (False,True):simulate_batch(cfg,eq,sl,gl,workers=8,engine='numba',boss_attacks=enabled)
    cfg['battle']['simulations']=3000;samples={False:[],True:[]}
    for _ in range(3):
        for enabled in (False,True):
            result=simulate_batch(cfg,eq,sl,gl,workers=8,engine='numba',boss_attacks=enabled)
            assert result['engine']=='numba_njit' and result['boss_attacks']==enabled
            samples[enabled].append(result['elapsed_seconds'])
    normal=statistics.median(samples[False]);boss=statistics.median(samples[True])
    print('3000 real-library battles, 8 threads, warm median (3 runs):',flush=True)
    print('ordinary:',round(normal,3),'s; Boss attacks:',round(boss,3),'s; ratio:',round(boss/normal,2),flush=True)
    print('samples:',samples,flush=True)

if __name__=='__main__':main()
