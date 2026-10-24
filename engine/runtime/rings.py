"""Live domain-ring restrictions and per-second lethal life loss."""
from backend.rings.store import gain_value

def refresh_rings(state):
    alive=sum(c.enabled and c.alive for c in state.characters)
    enemies=state.target.get('enemyCount',1)
    for c in state.characters:
        item=c.domain_ring
        if not item or not c.enabled:continue
        restriction=item['restriction'];stacks=1
        if restriction=='twoEnemies':stacks=int(enemies>=2 and (state.target_current_hp is None or state.target_current_hp>0))
        elif restriction=='missingParty':stacks=max(0,4-alive)
        elif restriction=='fullHealth':stacks=int(state.time==0 or c.current_hp is not None and c.current_hp>=c.maximum_hp)
        if not c.alive:stacks=0
        amount=gain_value(item)*stacks
        keys=['physicalBlock','magicBlock'] if item['gain']=='doubleBlock' else ['physicalDamage','magicDamage'] if item['gain']=='physicalMagicDamage' else [item['gain']]
        for key in keys:c.stats[key]=max(0,c.stats.get(key,0)-c.ring_gain_amount+amount)
        c.ring_gain_amount=amount

def process_ring_ticks(state):
    for c in state.characters:
        if not c.enabled or not c.alive or not c.domain_ring or c.domain_ring['restriction']!='sacrifice':continue
        while c.ring_next_tick<=state.time and c.current_hp>0:
            before=c.current_hp;c.current_hp=max(0,before-c.maximum_hp*.075);c.stats['hitPoint']=c.current_hp
            state.events.append(dict(time=c.ring_next_tick,type='sacrifice_tick',name=c.domain_ring['name']+'·域之环扣血',target_character=c.index,maximum_hp=c.maximum_hp,amount=before-c.current_hp,nominal_amount=c.maximum_hp*.075,before=before,after=c.current_hp))
            c.ring_next_tick+=1
