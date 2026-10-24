"""In-memory local batch jobs; library snapshots never change during a run."""
from threading import Lock,Thread
from multiprocessing import get_context
from engine.runtime.cancellation import SimulationCancelled
from time import perf_counter
from uuid import uuid4
from engine.runtime.batch import simulate_batch,batch_parameters
from engine.runtime.simulation import SingleBattle
from engine.runtime.initialization import BattleConfigurationError

class BatchJobs:
    def __init__(self):
        self.lock=Lock();self.jobs={}

    def start(self,config,equipment,skills,groups,*,boss_attacks=False):
        count,_=batch_parameters(config)
        battle_class=SingleBattle
        if boss_attacks:
            from engine.runtime.boss_simulation import BossBattle
            battle_class=BossBattle
        battle_class(config,equipment,skills,groups,seed=config.get('seed'),record_timeline=False)
        with self.lock:
            if any(j['status']=='running' for j in self.jobs.values()):
                raise BattleConfigurationError('已有批量模拟正在运行，请等待完成')
            for key in list(self.jobs)[:-9]:self.jobs.pop(key)
            key=uuid4().hex
            self.jobs[key]={'status':'running','completed':0,'total':count,'started':perf_counter(),'result':None,'cancel_event':get_context('spawn').Event()}
        def update(completed,total):
            with self.lock:self.jobs[key]['completed']=completed
        def work():
            try:
                result=simulate_batch(config,equipment,skills,groups,progress=update,cancel_event=self.jobs[key]['cancel_event'],boss_attacks=boss_attacks)
                with self.lock:
                    if self.jobs[key]['cancel_event'].is_set():
                        self.jobs[key].update(status='cancelled',elapsed_seconds=perf_counter()-self.jobs[key]['started'])
                    else:self.jobs[key].update(status='complete',result=result,elapsed_seconds=result['elapsed_seconds'])
            except SimulationCancelled:
                with self.lock:self.jobs[key].update(status='cancelled',elapsed_seconds=perf_counter()-self.jobs[key]['started'])
            except Exception as error:
                with self.lock:self.jobs[key].update(status='failed',error=str(error),elapsed_seconds=perf_counter()-self.jobs[key]['started'])
        Thread(target=work,daemon=True,name='batch-simulation').start()
        return {'job_id':key,'total':count}

    def get(self,key):
        with self.lock:
            job=self.jobs.get(key)
            if not job:raise BattleConfigurationError('批量任务不存在，服务重启会清除任务记录')
            return {k:v for k,v in job.items() if k not in ('started','cancel_event')}|{'elapsed_seconds':job.get('elapsed_seconds',perf_counter()-job['started'])}

    def cancel(self,key):
        with self.lock:
            job=self.jobs.get(key)
            if not job:raise BattleConfigurationError("批量任务不存在")
            if job["status"]=="running":job["cancel_event"].set()
        return self.get(key)
