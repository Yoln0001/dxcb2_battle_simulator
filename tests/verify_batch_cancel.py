from pathlib import Path
import sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.batch_jobs import BatchJobs

def main():
    config={'seed':1,'battle':{'duration':200,'simulations':10000},'target':{'hitPoint':1e12,'speed':100,'magicVulnerability':1},'characters':[{'job':'寒霜法师','enabled':True,'stats':{'constitution':100,'magic':100,'speed':100},'equipment':{},'skillGroup':'g'} for _ in range(4)]}
    skills={'s':{'job':'寒霜法师','name':'冰锥','damageType':'magic','cooldown':0,'hitRate':100,'criticalRate':0,'coefficients':{'magic':1},'effect':None}}
    groups={'g':{'job':'寒霜法师','entry':'n','subgroups':[{'id':'sub','nextGroup':'sub','skills':[{'id':'n','skillId':'s','next':''}]}]}}
    jobs=BatchJobs()
    for count in [10000,400]:
        config['battle']['simulations']=count
        key=jobs.start(config,{},skills,groups)['job_id']
        time.sleep(.05)
        jobs.cancel(key)
        deadline=time.monotonic()+10
        while jobs.get(key)['status']=='running' and time.monotonic()<deadline:time.sleep(.02)
        result=jobs.get(key)
        assert result['status']=='cancelled',result
        assert result['completed']<count and result['result'] is None
        assert 'cancel_event' not in result
    config['battle'].update(simulations=1,duration=1)
    key=jobs.start(config,{},skills,groups)['job_id']
    deadline=time.monotonic()+5
    while jobs.get(key)['status']=='running' and time.monotonic()<deadline:time.sleep(.02)
    assert jobs.get(key)['status']=='complete'
    print('PASS: parallel and serial cancellation stops computation and permits a new job')
if __name__=='__main__':main()
