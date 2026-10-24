"""TAS deterministic rewind and shared combat regression checks."""
import sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from verify_boss_combat import fixture
from engine.runtime.tas import TasSession
from engine.runtime.boss_simulation import BossBattle
from engine.runtime.initialization import BattleConfigurationError


def finish(session):
    for _ in range(1000):
        if session.done:return session.view()
        if session.battle.pending:
            if session.battle.boss_attacks:assert session.battle.boss_runtime[4][session.battle.pending-1,4,0]==0
            session.operate({'kind':'cast','character':session.battle.pending,'skill_id':'s'})
        else:session.operate({'kind':'step'})
    raise AssertionError('stuck TAS')


def main():
    cfg,eq,skills,groups=fixture()
    session=TasSession(cfg,eq,skills,groups)
    for i in range(1,5):session.operate({'kind':'mode','character':i,'mode':'auto'})
    result=finish(session)
    reference=BossBattle(cfg,eq,skills,groups,seed=cfg['seed']).run()
    assert result['total_damage']==reference['total_damage']
    assert result['snapshot']==reference['final_state'],(result['snapshot'],reference['final_state'])
    assert session.battle.frames==reference['timeline']
    print('PASS: all-auto TAS exactly matches seeded Boss timeline, state and damage')
    session=TasSession(cfg,eq,skills,groups)
    try:session.operate({'kind':'cast','character':1,'skill_id':'s'})
    except BattleConfigurationError:pass
    else:raise AssertionError('early cast')
    assert session.cursor==0
    while not session.battle.pending:session.operate({'kind':'step'})
    pending=session.view();assert pending['time']==1.5
    try:session.operate({'kind':'cast','character':pending['pending_character'],'skill_id':'invalid'})
    except BattleConfigurationError:pass
    else:raise AssertionError('unknown skill')
    assert session.view()['snapshot']==pending['snapshot']
    actor=session.battle.pending
    session.operate({'kind':'cast','character':actor,'skill_id':'s'})
    assert session.battle.state.time==1.5
    assert any(e['type']=='skill_released' and e['character']==actor for e in session.view()['events'])
    completed=finish(session);log=copy.deepcopy(session.log)
    session.seek(0);assert session.battle.state.time==0
    session.seek(round(completed['time']*10));restored=session.view()
    assert restored['snapshot']==completed['snapshot'] and restored['total_damage']==completed['total_damage']
    assert session.log==log
    session.seek(14);assert session.battle.state.time==1.4 and session.battle.pending is None
    session.operate({'kind':'step'});assert session.battle.pending
    assert session.horizon()==1.5 and len(session.log)<len(log)
    print('PASS: cooldown validation, same-tick decisions, deterministic rewind, future truncation')
    # Manual single-target healing can target a specific living teammate.
    cfg,eq,skills,groups=fixture();cfg['target']['selectedBoss']['skillGroup']['skills'][0]['baseValue']=0
    skills['heal']={**skills['s'],'name':'治疗','damageType':'none','coefficients':{'magic':1},'healingRecipient':'self'}
    session=TasSession(cfg,eq,skills,groups)
    while not session.battle.pending:session.operate({'kind':'step'})
    session.battle.state.characters[2].current_hp=100
    session.operate({'kind':'cast','character':session.battle.pending,'skill_id':'heal','target_character':3})
    assert session.battle.state.characters[2].current_hp==200
    # Manual actions continue after the original group ends.
    skills['group']={**skills['heal'],'name':'凝神静气','healingRecipient':'allAllies'}
    session=TasSession(cfg,eq,skills,groups)
    while not session.battle.pending:session.operate({'kind':'step'})
    for c in session.battle.state.characters:c.current_hp=100
    actor=session.battle.pending
    try:session.operate({'kind':'cast','character':actor,'skill_id':'group','target_character':1})
    except BattleConfigurationError:pass
    else:raise AssertionError('group heal must not accept a single target')
    session.operate({'kind':'cast','character':actor,'skill_id':'group'})
    assert all(c.current_hp==200 for c in session.battle.state.characters)
    assert sum(e['type']=='healing' for e in session.view()['events'])==4
    print('PASS: group healing restores all living allies and rejects single-target overrides')
    groups['g']['subgroups'][0].pop('nextGroup')
    session=TasSession(cfg,eq,skills,groups);finish(session)
    assert len(session.view()['decisions'])>=8
    print('PASS: explicit healing target and repeat manual casts beyond finite skill groups')
    cfg['target'].pop('selectedBoss');session=TasSession(cfg,eq,skills,groups);finish(session)
    assert not session.battle.boss_attacks
    print('PASS: Boss-free TAS works with explicit warning')
    for c in cfg['characters']:c.pop('skillGroup',None)
    session=TasSession(cfg,eq,skills,{})
    try:session.operate({'kind':'mode','character':1,'mode':'auto'})
    except BattleConfigurationError:pass
    else:raise AssertionError('auto without group')
    finish(session)
    assert session.view()['decisions']
    print('PASS: manual TAS needs no skill group; automatic mode validates a group')
    # Incoming stun suppresses prompts; death prevents later manual actions.
    cfg,eq,skills,groups=fixture()
    attack=cfg['target']['selectedBoss']['skillGroup']['skills'][0]
    attack.update(baseValue=1,targeting='all',effect={'kind':'debuff','type':'stun','baseValue':0,'duration':3,'applicationRate':1000,'coefficients':dict.fromkeys(('strength','magic','technique','speed'),0)})
    session=TasSession(cfg,eq,skills,groups);finish(session)
    print('PASS: stunned characters cannot manually cast')
    cfg,eq,skills,groups=fixture();cfg['target'].pop('selectedBoss')
    session=TasSession(cfg,eq,skills,groups)
    while not session.battle.pending:session.operate({'kind':'step'})
    actor=session.battle.pending
    session.operate({'kind':'hold','character':actor})
    assert session.battle.state.characters[actor-1].last_action_at is None
    assert any(e['type']=='tas_hold' for e in session.view()['events'])
    session.seek(14)
    session.seek(15)
    assert any(e['type']=='tas_hold' for e in session.view()['events'])
    print('PASS: holding preserves readiness and rewinds deterministically')

if __name__=='__main__':main()
