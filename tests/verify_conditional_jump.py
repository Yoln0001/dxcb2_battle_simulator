from engine.runtime.simulation import SkillSequence
from backend.skill_groups.validation import validate_group

def main():
    condition = {'equipmentId':'weapon', 'effectIndex':0, 'effectName':'魔力增幅'}
    group={'schemaVersion':2,'id':'g','name':'条件跳转','job':'寒霜法师','entry':'a','subgroups':[{'id':'one','nextGroup':'one','skills':[{'id':'a','skillId':'s','next':'c','jumpCondition':condition},{'id':'b','skillId':'s','next':''},{'id':'c','skillId':'s','next':'a'}]}]}
    stored=validate_group(group)
    assert stored['subgroups'][0]['skills'][0]['jumpCondition']==condition
    skills={'s':{'job':'寒霜法师'}}
    sequence=SkillSequence(stored,skills,'寒霜法师')
    sequence.advance();assert sequence.current=='b'
    row={'name':'魔力增幅'};item={'id':'weapon','triggerEffects':[row]}
    sequence.current='a';sequence.advance([(item,'weapon',row)]);assert sequence.current=='c'
    sequence.current='a';sequence.advance([({'id':'other','triggerEffects':[row]},'armor',row)]);assert sequence.current=='b'
    sequence.current='c';sequence.advance();assert sequence.current=='a'
    group['subgroups'][0]['skills'][0].pop('jumpCondition')
    sequence=SkillSequence(validate_group(group),skills,'寒霜法师');sequence.advance();assert sequence.current=='c'
    print('PASS: condition persistence, success/failure, wrong equipment, and legacy unconditional jumps')

if __name__=='__main__':main()
