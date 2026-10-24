# Boss status layout includes armor and resistance decay (14 status types).
"""Nopython combat loop. No dictionaries, strings, logs or Python objects per tick."""
import math
import numpy as np
from numba import njit,prange
from .rng import uniform,shuffle
from . import boss as boss_combat

@njit(cache=True)
def dot(a,b):
    value=0.0
    for k in range(len(a)):value+=a[k]*b[k]
    return value

@njit(cache=True)
def add_time(a,b):return round(a+b,12)

@njit(cache=True)
def ratio(stats):
    value=max(stats[0]-stats[18],1.0)/(stats[3]+1.0)*10.0
    # Correct a binary rounding error at exact decimal tenth boundaries.
    nearest=round(value)
    if abs(value-nearest)<1e-12:value=float(nearest)
    return min(3.0,math.floor(value)/10.0)

@njit(cache=True)
def damage(base,s,t,dtype,critical=1.0,race=1.0,defense=True):
    value=base*(1+s[12+dtype]/100)*critical*race*(1+s[15+dtype]/100)*t[5+dtype]
    if defense:value*=50/(max(t[1+dtype]-s[9+dtype],0)+50)
    return max(1.0,value*(1-t[8+dtype]/100))

@njit(cache=True)
def select_target_index(rule,actor,stats,alive):
    if rule==0:return actor
    attribute=5 if rule<=2 else 27 if rule<=4 else 28
    highest=rule%2==0
    chosen=-1
    for c in range(4):
        if alive[c] and (chosen<0 or (stats[c,attribute]>stats[chosen,attribute] if highest else stats[c,attribute]<stats[chosen,attribute])):
            chosen=c
    return chosen

@njit(cache=True)
def apply_buff(eid,actor,time,stats,alive,delta,active,layers,expiry,order,generation,emeta,econ,ebase,counter,forced_target=-1):
    meta=emeta[eid];name=int(meta[1]);recipients=np.zeros(4,np.int64)
    for c in range(4):
        if alive[c] and (meta[2]==1 or c==(forced_target if forced_target>=0 else actor)):
            recipients[c]=1
            layers[c,name]=min((layers[c,name] if active[c,name] else 0)+1,int(meta[5]))
            if active[c,name]:
                for a in range(stats.shape[1]):stats[c,a]=max(0.0,stats[c,a]-delta[c,name,a])
                active[c,name]=0
    source=stats[actor].copy()
    amounts=np.zeros(stats.shape[1])
    for a in range(stats.shape[1]):amounts[a]=ebase[eid,a]+dot(source,econ[eid,a])
    for c in range(4):
        if recipients[c]:
            for a in range(stats.shape[1]):
                delta[c,name,a]=amounts[a]*layers[c,name]
                stats[c,a]+=delta[c,name,a]
            counter+=1;active[c,name]=1;order[c,name]=counter;generation[c,name]+=1
            expiry[c,name]=add_time(time,meta[4]) if meta[4]>0 else math.inf
    return counter

@njit(cache=True)
def apply_debuff(eid,actor,time,s,t,immune,rng,equipment,emeta,elinear,ebase,boss,serial):
    meta=emeta[eid];kind=int(meta[7])
    if immune[kind]:return serial
    if not equipment:
        chance=min(1.0,max(0.0,(meta[8]+s[11]-t[2]/10)/100))
        if uniform(rng)>=chance:return serial
    if boss[kind,0]==0:serial+=1;boss[kind,6]=serial
    boss[kind,0]=1;boss[kind,1]=actor;boss[kind,2]=add_time(time,meta[4]);boss[kind,3]=add_time(time,1)
    boss[kind,4]=time
    if kind in (3,5,6):boss[kind,5]=ebase[eid,0]+dot(s,elinear[eid])
    if kind==0 or kind==7:
        base=ebase[eid,0]+dot(s,elinear[eid])
        boss[kind,5]=max(1.0,base*(1+s[14]/100)*(1+s[17]/100)*t[7]*(1-t[10]/100))
    return serial

@njit(cache=True)
def refresh_rings(stats,alive,hp,maximum,rings,target_hp):
    party_size=np.sum(alive)
    for c in range(4):
        restriction=int(rings[c,0])
        if restriction<0:continue
        stacks=1
        if restriction==1:stacks=int(rings[c,6]>=2 and target_hp>0)
        elif restriction==2:stacks=max(0,4-party_size)
        elif restriction==3:stacks=int(hp[c]>=maximum[c])
        if not alive[c]:stacks=0
        amount=rings[c,3]*stacks
        if amount==rings[c,4]:continue
        # Refresh by delta so unrelated bonuses, buffs and conversions remain intact.
        for column in (1,2):
            attribute=int(rings[c,column])
            if attribute>=0:stats[c,attribute]=max(0.0,stats[c,attribute]-rings[c,4]+amount)
        rings[c,4]=amount

@njit(cache=True)
def battle(initial,enabled,health,opening,opening_active,opening_order,target,immune,settings,
           smeta,scoef,nodes,entries,proc,ranges,emeta,econ,ebase,elinear,initial_regen,initial_rings,rng,boss_data=None):
    regen=initial_regen.copy();rings=initial_rings.copy()
    if boss_data is not None:boss_runtime=boss_combat.initial_state(boss_data)
    stats=initial.copy();alive=enabled.copy();maximum=health[:,0].copy();hp=health[:,1].copy()
    for c in range(4):
        if hp[c]<=0:alive[c]=0
    delta=opening.copy();active=opening_active.copy();layers=opening_active.copy()
    expiry=np.full(active.shape,math.inf);order=opening_order.copy();generation=np.zeros(active.shape,np.int64)
    counter=int(np.max(order));boss=np.zeros((len(immune),7));boss_serial=0
    current=entries.copy();last=np.zeros(4);cooldown=np.zeros(4);forced=np.full(4,-1.0);waiting=np.full(4,-1.0);operating=np.full(4,-1.0);operation_target=np.full(4,-1)
    totals=target[15:19].copy();counts=np.zeros(len(proc),np.int64);total=np.sum(totals);target_hp=target[14]
    kill_next=settings[8];kill_strategy=int(settings[12]);survival_at_all_kill=np.zeros(4,np.int64);survival_captured=False
    owner=int(settings[1]);contract_next=settings[10];contract_ticks=0;contract_active=owner>=0
    if owner>=0 and not alive[owner]:contract_active=False
    events=np.zeros((active.size+len(immune)+3,4),np.float64);last_step=int(settings[0]*10+1e-9)
    for step in range(1,last_step+1):
        if target_hp<=0:break
        time=step/10.0
        refresh_rings(stats,alive,hp,maximum,rings,target_hp)
        if step%10==0:
            for pos in range(13,len(settings),2):
                value=settings[pos+1];total+=value;totals[int(settings[pos])]+=value;target_hp=max(0.0,target_hp-value)
        for dot_kind in (0,7):
            if boss[dot_kind,0] and boss[dot_kind,3]<=time and boss[dot_kind,3]<=boss[dot_kind,2]:
                value=boss[dot_kind,5];total+=value;totals[int(boss[dot_kind,1])]+=value;target_hp=max(0.0,target_hp-value)
                boss[dot_kind,3]=add_time(boss[dot_kind,3],1)
                if boss[dot_kind,2]<=time:boss[dot_kind,0]=0
        if target_hp<=0:break
        # Boss status and self-buff amounts include all active stacks.
        if boss_data is not None:
            incoming,healing=boss_combat.periodic(time,stats,hp,maximum,alive,boss_runtime)
            target_hp=min(target[0],target_hp+healing)
            if owner>=0 and not alive[owner]:contract_active=False
        if kill_next>=0 and time>=kill_next:
            if kill_strategy==0 and not survival_captured:
                survival_at_all_kill=alive.copy();survival_captured=True
            chosen=-1
            if kill_strategy==1:
                count=np.sum(alive)
                if count>0:
                    pick=min(int(count)-1,int(uniform(rng)*count))
                    for c in range(4):
                        if alive[c]:
                            if pick==0:chosen=c;break
                            pick-=1
            elif kill_strategy in (2,3):
                for c in range(4):
                    if alive[c] and (chosen<0 or (hp[c]<hp[chosen] if kill_strategy==2 else hp[c]>hp[chosen])):chosen=c
            for c in range(4):
                if alive[c] and (kill_strategy==0 or c==chosen):hp[c]=0.0;stats[c,5]=0.0;alive[c]=0
            if owner>=0 and not alive[owner]:contract_active=False
            kill_next=add_time(kill_next,settings[8])
            if not np.any(alive):break
        # Ring sacrifice is lethal and resolves before contract sacrifice and healing.
        for c in range(4):
            if alive[c] and rings[c,0]==6:
                while rings[c,5]<=time and hp[c]>0:
                    hp[c]=max(0.0,hp[c]-maximum[c]*.075);stats[c,5]=hp[c]
                    rings[c,5]+=1
        if settings[3] and step%10==0:
            for c in range(4):
                if alive[c]:
                    hp[c]=max(0.0,hp[c]-maximum[c]*.05);stats[c,5]=hp[c]
                    if hp[c]<=0:
                        alive[c]=0
                        if c==owner:contract_active=False
        for c in range(4):
            if alive[c] and hp[c]<=0:
                alive[c]=0
                if c==owner:contract_active=False
        for c in range(4):
            if alive[c]:
                for b in range(regen.shape[1]):
                    if regen[c,b,3] and regen[c,b,1]<=time and regen[c,b,1]<=regen[c,b,2]:
                        hp[c]=min(maximum[c],hp[c]+regen[c,b,0]*health[c,4]);stats[c,5]=hp[c]
                        regen[c,b,1]=add_time(regen[c,b,1],1)
                        if regen[c,b,1]>regen[c,b,2]:regen[c,b,3]=0
        count=0
        # Expiry blocks preserve each character's buff insertion order.
        for c in range(4):
            begin=count
            for b in range(active.shape[1]):
                if active[c,b] and expiry[c,b]<=time:
                    events[count]=np.array([0,c,b,generation[c,b]],np.float64);count+=1
            for i in range(begin+1,count):
                j=i
                while j>begin and order[c,int(events[j,2])]<order[c,int(events[j-1,2])]:
                    tmp=events[j].copy();events[j]=events[j-1];events[j-1]=tmp;j-=1
        begin=count
        for k in range(len(immune)):
            if boss[k,0]:
                if boss[k,2]<=time and not ((k==0 or k==7) and boss[k,3]<=boss[k,2]):
                    events[count]=np.array([1,k,boss[k,4],boss[k,6]],np.float64);count+=1
                if (k==0 or k==7) and boss[k,3]<=time and boss[k,3]<=boss[k,2]:
                    pass  # DOT has already resolved at the start of the tick.
        for i in range(begin+1,count):
            j=i
            while j>begin and events[j,3]<events[j-1,3]:
                tmp=events[j].copy();events[j]=events[j-1];events[j-1]=tmp;j-=1
        if contract_active and contract_next<=time:
            events[count,0]=3;events[count,1]=0;events[count,2]=0;events[count,3]=0;count+=1
        has_current=False
        for c in range(4):
            if current[c]>=0:has_current=True;break
        if has_current:
            events[count,0]=4;events[count,1]=0;events[count,2]=0;events[count,3]=0;count+=1
        if boss_data is not None:
            if boss_runtime[1][0]>=0 and boss_combat.deadline(boss_runtime,boss)<=time:
                events[count,0]=5;events[count,1]=0;events[count,2]=0;events[count,3]=0;count+=1
        shuffle(rng,events,count)
        for e in range(count):
            refresh_rings(stats,alive,hp,maximum,rings,target_hp)
            kind=int(events[e,0]);index=int(events[e,1])
            if kind==0:
                b=int(events[e,2])
                if active[index,b] and generation[index,b]==int(events[e,3]):
                    for a in range(stats.shape[1]):stats[index,a]=max(0.0,stats[index,a]-delta[index,b,a])
                    active[index,b]=0
            elif kind==1:
                if boss[index,0] and boss[index,4]==events[e,2] and boss[index,2]<=time:boss[index,0]=0
            elif kind==2:
                if boss[index,0] and boss[index,4]==events[e,2] and boss[index,3]<=time:
                    value=boss[index,5];total+=value;totals[int(boss[index,1])]+=value;target_hp=max(0.0,target_hp-value)
                    boss[index,3]=add_time(boss[index,3],1)
                    if boss[index,2]<=time:boss[index,0]=0
            elif kind==3:
                if not contract_active:continue
                contract_kind=int(settings[11])
                if contract_kind==4 or contract_kind==5:
                    extra=4.0 if contract_kind==4 and contract_ticks==0 else 1.0
                    if contract_kind==5:extra=1+.3*min(4,math.floor(max(0.0,1-target_hp/target[0])*4+1e-9))
                    if not immune[0]:
                        boss[0,0]=1;boss[0,1]=owner;boss[0,2]=add_time(time,1);boss[0,3]=add_time(time,1);boss[0,4]=time
                        boss[0,5]=max(1.0,stats[owner,2]*settings[2]*extra*(1+stats[owner,14]/100)*(1+stats[owner,17]/100)*target[7]*(1-target[10]/100))
                    contract_ticks+=1;contract_next=add_time(contract_next,settings[9])
                    continue
                attribute=1 if contract_kind in (0,6,7) else 3 if contract_kind in (8,9,10) else 0
                source=stats[owner,attribute]
                if contract_kind in (0,3,10):
                    source=0.0
                    for c in range(4):
                        if alive[c]:source+=stats[c,attribute]
                extra=4.0 if contract_kind in (1,6,8) and contract_ticks==0 else 1.0
                if contract_kind in (2,7,9):extra=1+.3*min(4,math.floor(max(0.0,1-target_hp/target[0])*4+1e-9))
                dtype=1 if contract_kind in (0,6,7) else 0
                value=max(1.0,source*settings[2]*extra*(1+stats[owner,12+dtype]/100)*(1+stats[owner,15+dtype]/100)*target[5+dtype]*(1-target[8+dtype]/100))
                total+=value;totals[owner]+=value;target_hp=max(0.0,target_hp-value)
                contract_ticks+=1;contract_next=add_time(contract_next,settings[9])
            elif kind==5 and boss_data is not None:
                released,hits,incoming,applied,target_hp,received_triggers=boss_combat.act(time,target_hp,target,stats,hp,maximum,alive,boss,boss_data,boss_runtime,rng,(proc,ranges,emeta,econ))
                for c in range(4):
                    if hp[c]<=0:alive[c]=0
                if owner>=0 and not alive[owner]:contract_active=False
                if released>=0:
                    for c in range(4):
                        if not alive[c] or not hits[c]:continue
                        trigger=int(received_triggers[c])
                        if trigger>=0:counts[trigger]+=1
                        if trigger<0:continue
                        eid=int(proc[trigger,2]);ek=int(emeta[eid,0]);snap=stats[c].copy()
                        if ek==2:
                            source=snap.copy();source[22]=maximum[c]-hp[c]
                            for a in range(stats.shape[1]):snap[a]+=dot(source,econ[eid,a])
                        elif ek==1:
                            counter=apply_buff(eid,c,time,stats,alive,delta,active,layers,expiry,order,generation,emeta,econ,ebase,counter)
                        elif ek==3 or ek==4:
                            value=damage(dot(snap,elinear[eid]),snap,target,ek-3,1.,1.,False)
                            total+=value;totals[c]+=value;target_hp=max(0.,target_hp-value)
                        elif ek==8:
                            name=int(emeta[eid,1]);value=(ebase[eid,0]+dot(stats[c],elinear[eid]))*(1+stats[c,20]/100)*(1+stats[c,21]/100)
                            for recipient in range(4):
                                if alive[recipient] and (emeta[eid,2] or recipient==c):
                                    regen[recipient,name,0]=value;regen[recipient,name,1]=add_time(time,1)
                                    regen[recipient,name,2]=add_time(time,emeta[eid,4]) if emeta[eid,4]>0 else math.inf;regen[recipient,name,3]=1
                        elif ek==5:forced[c]=add_time(time,.5)
                        elif ek==6:boss_serial=apply_debuff(eid,c,time,snap,target,immune,rng,True,emeta,elinear,ebase,boss,boss_serial)
                        elif ek==7:
                            value=dot(snap,elinear[eid])*(1+snap[20]/100)*(1+snap[21]/100)
                            for recipient in range(4):
                                if alive[recipient] and (emeta[eid,2] or recipient==c):
                                    hp[recipient]=min(maximum[recipient],hp[recipient]+value*health[recipient,3]);stats[recipient,5]=hp[recipient]
            else:
                for c in range(4):
                    refresh_rings(stats,alive,hp,maximum,rings,target_hp)
                    node=int(current[c])
                    if not alive[c] or node<0:continue
                    if boss_data is not None:
                        if boss_combat.blocked(c,boss_runtime):continue
                    finished_wait=False
                    finishing_operation=operating[c]>=0
                    matched_target=-1
                    if finishing_operation:
                        if time<operating[c]:continue
                        operating[c]=-1
                        matched_target=int(operation_target[c])
                        if matched_target<0 or not alive[matched_target]:continue
                    if waiting[c]>=0:
                        if time<waiting[c]:continue
                        waiting[c]=-1;current[c]=nodes[node,1] if nodes[node,3]==-1 else nodes[node,2];node=int(current[c]);finished_wait=True
                        if node<0:continue
                    wait=max(.5,add_time(1.5+cooldown[c]+stats[c,29],ratio(stats[c])))
                    ordinary=0.1 if last[c]==0 and settings[4+c] else add_time(last[c],wait)
                    deadline=forced[c] if forced[c]>=0 else ordinary
                    if not finishing_operation and not finished_wait and time<deadline:continue
                    if not finishing_operation and nodes[node,7]>=0:
                        chosen=-1
                        for candidate in range(int(nodes[node,7]),int(nodes[node,8])):
                            condition=int(nodes[candidate,9]);low=False
                            for ally in range(4):
                                if ally!=c and alive[ally] and maximum[ally]>0 and hp[ally]/maximum[ally]*100<nodes[candidate,10]:low=True
                            if condition==4:
                                member=-1
                                for ally in range(4):
                                    if not alive[ally] or (not nodes[candidate,15] and ally==c):continue
                                    k=int(nodes[candidate,11]);source_skill=int(nodes[candidate,12])
                                    if k>=0:
                                        if boss_data is None:continue
                                        status=boss_runtime[4][ally,k]
                                        if not status[0] or source_skill<0 or status[5]!=source_skill:continue
                                        if time+1e-9<add_time(status[6],nodes[candidate,17]):continue
                                    b=int(nodes[candidate,13]);attribute=int(nodes[candidate,14])
                                    if b>=0:
                                        present=regen[ally,b,3]>0 if attribute==-2 else active[ally,b]>0 and delta[ally,b,attribute]!=0
                                        if present:continue
                                    if member<0 or hp[ally]<hp[member]:member=ally
                                if member>=0:
                                    chosen=candidate;matched_target=member;break
                            if condition==0 or condition==1 and low or condition==2 and not low:
                                chosen=candidate;break
                        if chosen<0:continue
                        node=chosen;current[c]=node
                    elif not finishing_operation and nodes[node,4]>=0:
                        matched=False
                        for ally in range(4):
                            if ally!=c and alive[ally] and maximum[ally]>0 and hp[ally]/maximum[ally]*100<nodes[node,4]:matched=True
                        node=int(nodes[node,5] if matched else nodes[node,6]);current[c]=node
                    if not finishing_operation and nodes[node,18]>0:
                        operating[c]=add_time(time,nodes[node,18]);operation_target[c]=matched_target;forced[c]=-1
                        continue
                    skill=int(nodes[node,0]);dtype=int(smeta[skill,0]);trigger=-1
                    if dtype==3:
                        if not finished_wait and time<ordinary:continue
                        waiting[c]=add_time(time,smeta[skill,1]);forced[c]=-1
                        continue
                    for p in range(ranges[c,0],ranges[c,1]):
                        if int(proc[p,0])==dtype and uniform(rng)<proc[p,1]/100:
                            trigger=p;counts[p]+=1;break
                    eid=int(proc[trigger,2]) if trigger>=0 else -1
                    snap=stats[c].copy()
                    if eid>=0 and emeta[eid,0]==2:
                        source=snap.copy();source[22]=maximum[c]-hp[c]
                        for a in range(stats.shape[1]):snap[a]+=dot(source,econ[eid,a])
                    skill_target=(matched_target if nodes[node,16] and matched_target>=0 else select_target_index(1,c,stats,alive)) if dtype==2 else c
                    hit=True
                    if dtype<2:
                        chance=min(1.0,max(0.0,(smeta[skill,2]+snap[8]-snap[30]-target[4]+snap[2]/target[3]*30)/100))
                        hit=uniform(rng)<chance
                        if hit:
                            critical=uniform(rng)<min(1.0,(smeta[skill,3]+snap[7]+snap[2]/20)/100)
                            crit=1.5+snap[19]/100 if critical else 1.0
                            value=damage(dot(snap,scoef[skill]),snap,target,dtype,crit,smeta[skill,4],True)
                            total+=value;totals[c]+=value;target_hp=max(0.0,target_hp-value)
                            lifesteal=snap[23+dtype+2*int(smeta[skill,7])]+smeta[skill,9]
                            if lifesteal>0:
                                hp[c]=min(maximum[c],hp[c]+value*lifesteal/100*health[c,2]);stats[c,5]=hp[c]
                    else:
                        value=dot(snap,scoef[skill])*(1+snap[20]/100)*(1+snap[21]/100)
                        for recipient in range(4):
                            if alive[recipient] and (smeta[skill,5] or recipient==skill_target):
                                hp[recipient]=min(maximum[recipient],hp[recipient]+value*health[recipient,3]);stats[recipient,5]=hp[recipient]
                    if eid>=0 and emeta[eid,0]==1:
                        counter=apply_buff(eid,c,time,stats,alive,delta,active,layers,expiry,order,generation,emeta,econ,ebase,counter)
                    if eid>=0 and emeta[eid,0]==8:
                        name=int(emeta[eid,1]);value=(ebase[eid,0]+dot(stats[c],elinear[eid]))*(1+stats[c,20]/100)*(1+stats[c,21]/100)
                        for recipient in range(4):
                            if alive[recipient] and (emeta[eid,2] or recipient==c):
                                regen[recipient,name,0]=value;regen[recipient,name,1]=add_time(time,1)
                                regen[recipient,name,2]=add_time(time,emeta[eid,4]) if emeta[eid,4]>0 else math.inf;regen[recipient,name,3]=1
                    buff_target=skill_target if smeta[skill,10] else c
                    if smeta[skill,11]:
                        candidates=alive.copy();candidates[c]=0
                        buff_target=select_target_index(1,c,stats,candidates)
                    skill_effect=int(smeta[skill,6])
                    if skill_effect>=0:
                        if emeta[skill_effect,0]==1:
                            if uniform(rng)<emeta[skill_effect,6]/100 and (not smeta[skill,11] or buff_target>=0):
                                counter=apply_buff(skill_effect,c,time,stats,alive,delta,active,layers,expiry,order,generation,emeta,econ,ebase,counter,buff_target)
                        elif emeta[skill_effect,0]==8:
                            if uniform(rng)<emeta[skill_effect,6]/100 and (not smeta[skill,11] or buff_target>=0):
                                name=int(emeta[skill_effect,1])
                                value=(ebase[skill_effect,0]+dot(stats[c],elinear[skill_effect]))*(1+stats[c,20]/100)*(1+stats[c,21]/100)
                                for recipient in range(4):
                                    if alive[recipient] and (emeta[skill_effect,2] or recipient==buff_target):
                                        regen[recipient,name,0]=value;regen[recipient,name,1]=add_time(time,1)
                                        regen[recipient,name,2]=add_time(time,emeta[skill_effect,4]) if emeta[skill_effect,4]>0 else math.inf
                                        regen[recipient,name,3]=1
                        elif emeta[skill_effect,0]==6 and hit:
                            boss_serial=apply_debuff(skill_effect,c,time,snap,target,immune,rng,False,emeta,elinear,ebase,boss,boss_serial)
                    if eid>=0:
                        ek=int(emeta[eid,0])
                        if ek==3 or ek==4:
                            value=damage(dot(snap,elinear[eid]),snap,target,ek-3,1.0,1.0,False)
                            total+=value;totals[c]+=value;target_hp=max(0.0,target_hp-value)
                        elif ek==7:
                            value=dot(snap,elinear[eid])*(1+snap[20]/100)*(1+snap[21]/100)
                            for recipient in range(4):
                                if alive[recipient] and (emeta[eid,2] or recipient==c):
                                    hp[recipient]=min(maximum[recipient],hp[recipient]+value*health[recipient,3]);stats[recipient,5]=hp[recipient]
                        elif ek==6 and hit:
                            boss_serial=apply_debuff(eid,c,time,snap,target,immune,rng,True,emeta,elinear,ebase,boss,boss_serial)
                    last[c]=time;cooldown[c]=smeta[skill,1];forced[c]=-1.0
                    condition=int(nodes[node,3]);matched=condition==-1 or (trigger>=0 and condition==trigger)
                    current[c]=nodes[node,1] if matched else nodes[node,2]
                    if eid>=0 and emeta[eid,0]==5:forced[c]=add_time(time,.5)
        if not np.any(alive) or target_hp<=0:break
    if not survival_captured:survival_at_all_kill=alive.copy()
    return total,target_hp<=0,totals,counts,stats,hp,alive,survival_at_all_kill

@njit(cache=True,parallel=True,nogil=True)
def chunk(initial,enabled,health,opening,opening_active,opening_order,target,immune,settings,
          smeta,scoef,nodes,entries,proc,ranges,emeta,econ,ebase,elinear,initial_regen,initial_rings,random_states,boss_data=None):
    n=len(random_states);damage_out=np.zeros(n);passed=np.zeros(n,np.int64)
    all_alive=np.zeros(n,np.int64);character_alive=np.zeros((n,4),np.int64)
    characters=np.zeros((n,4));counts=np.zeros((n,len(proc)),np.int64)
    for i in prange(n):
        total,success,values,procs,_,_,_,survivors=battle(initial,enabled,health,opening,opening_active,opening_order,target,immune,settings,
                                             smeta,scoef,nodes,entries,proc,ranges,emeta,econ,ebase,elinear,initial_regen,initial_rings,random_states[i].copy(),boss_data)
        damage_out[i]=total;passed[i]=success;characters[i]=values;counts[i]=procs
        all_alive[i]=np.all(survivors);character_alive[i]=survivors
    return damage_out,passed,characters,counts,all_alive,character_alive
