const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const root=process.argv[2]||require("path").resolve(__dirname,"..");const model=require(root+'/frontend/js/equipment/model.js');
const nodes=[],named=new Map();
class Node{
 constructor(tag){this.tag=tag;this.children=[];this.handlers={};this.dataset={};this.classList={add(){},remove(){},toggle(){}};this.checked=false;this.defaultValue='';this.value='';this.textContent='';nodes.push(this);}
 set name(n){this._name=n;named.set(n,this);}get name(){return this._name;}
 get lastChild(){return this.children.at(-1);}append(...children){this.children.push(...children);}replaceChildren(...children){this.children=children;}
 setAttribute(){}addEventListener(kind,fn){(this.handlers[kind]??=[]).push(fn);}querySelectorAll(selector){const all=this.children.flatMap(c=>[c,...c.querySelectorAll('*')]);return selector==='[data-matrix]'?all.filter(c=>c.dataset.matrix):all;}
 get elements(){return {namedItem:n=>named.get(n)};}reportValidity(){return true;}
 reset(){for(const x of named.values()){x.checked=false;x.value=x.tag==='select'?(x.children[0]?.value||''):x.defaultValue;}}
 close(){}showModal(){}click(){for(const fn of this.handlers.click||[])fn();}
}
const toast=new Node('div'),open=new Node('button'),data={};
const context={document:{createElement:tag=>new Node(tag),body:new Node('body'),querySelector:s=>s==='#toast'?toast:open},window:{showToast(){},EquipmentModel:model,SkillModel:require(root+'/frontend/js/skills/model.js')},location:{protocol:'file:'},localStorage:{getItem:k=>data[k]??null,setItem:(k,v)=>data[k]=v},setTimeout:()=>0,clearTimeout(){},confirm:()=>true,crypto,console,structuredClone};
vm.createContext(context);vm.runInContext(fs.readFileSync(root+'/frontend/js/equipment/editor.js','utf8'),context);
(async()=>{
 const form=nodes.find(n=>n.id==='equipment-form'),create=nodes.find(n=>n.textContent==='＋ 创建装备');
 for(const kind of ['none','amplify','magicTrueDamage','immediateAction','debuff','buff']){
  create.click();named.get('startEnabled').checked=true;named.get('triggerEnabled').checked=true;named.get('name').value='测试 '+kind;named.get('effectKind').value=kind;named.get('effectName').value='开战 '+kind;named.get('triggerEffectName').value='触发 '+kind;named.get('attackType').value='magic';
  if(['amplify','buff'].includes(kind)){named.get(kind+'-enabled-strength').checked=true;named.get(kind+'-strength-magic').value='170';}
  if(kind==='amplify')named.get('amplify-strength-lostHitPoint').value='45';
  for(const fn of form.handlers.change||[])fn();
  await form.handlers.submit[0]({preventDefault(){}});
  const saved=JSON.parse(data['dungeon2-equipment-library-v1']).equipment;
  const item=saved.find(x=>x.name==='测试 '+kind);assert.ok(item,kind);
  assert.equal(item.effect?.kind||'none',kind);if(kind==='amplify'){assert.equal(item.effect.conversions[0].coefficients.lostHitPoint,0.45);assert.equal(named.get('amplify-strength-lostHitPoint').value,45);}assert.equal(item.effectName,'开战 '+kind);assert.equal(item.triggerEffectName,'触发 '+kind);assert.equal(item.attackType,'magic');assert.equal(item.startingBuff.enabled,true);assert.equal(item.triggerEnabled,true);assert.equal(named.get('effectName').value,item.effectName);assert.equal(named.get('triggerEffectName').value,item.triggerEffectName);
  if(['amplify','buff'].includes(kind))assert.equal(item.effect.conversions[0].coefficients.magic,1.7);
 }
 assert.equal(JSON.parse(data['dungeon2-equipment-library-v1']).equipment.length,6);
 const duplicate=nodes.find(n=>n.textContent==='另存为副本');duplicate.click();await form.handlers.submit[0]({preventDefault(){}});assert.equal(JSON.parse(data['dungeon2-equipment-library-v1']).equipment.length,7);
 named.get('startEnabled').checked=false;named.get('triggerEnabled').checked=false;
 for(const fn of form.handlers.change||[])fn();
 assert.equal(named.get('start-magic').disabled,true);assert.equal(named.get('triggerRate').disabled,true);
 await form.handlers.submit[0]({preventDefault(){}});
 const closed=JSON.parse(data['dungeon2-equipment-library-v1']).equipment.find(x=>x.name.endsWith('（副本）'));
 assert.equal(closed.startingBuff.enabled,false);assert.equal(closed.triggerEnabled,false);assert.equal(closed.effect.kind,'buff');
 assert.equal(named.get('startEnabled').checked,false);assert.equal(named.get('triggerEnabled').checked,false);
 create.click();named.get('name').value='双触发装备';named.get('triggerEnabled').checked=true;
 named.get('triggerEffectName').value='物理特效';named.get('attackType').value='physical';named.get('effectKind').value='immediateAction';named.get('triggerRate').value='30';
 nodes.filter(n=>n.textContent==='＋ 添加特效').at(-1).click();
 named.get('triggerEffectName').value='魔法特效';named.get('attackType').value='magic';named.get('effectKind').value='magicTrueDamage';named.get('triggerRate').value='60';named.get('true-magic').value='200';
 nodes.filter(n=>n.tag==='button'&&n.textContent==='特效 1 · 物理特效').at(-1).click();
 assert.equal(named.get('triggerEffectName').value,'物理特效');assert.equal(named.get('triggerRate').value,30);
 await form.handlers.submit[0]({preventDefault(){}});
 const multi=JSON.parse(data['dungeon2-equipment-library-v1']).equipment.find(x=>x.name==='双触发装备');
 assert.equal(multi.triggerEffects.length,2);assert.equal(multi.triggerEffects[0].triggerType,'physical');assert.equal(multi.triggerEffects[1].triggerType,'magic');assert.equal(multi.triggerEffects[1].effect.coefficients.magic,2);
 nodes.filter(n=>n.tag==='button'&&n.textContent==='特效 2 · 魔法特效').at(-1).click();assert.equal(named.get('triggerRate').value,60);
 nodes.filter(n=>n.textContent==='删除当前特效').at(-1).click();await form.handlers.submit[0]({preventDefault(){}});
 assert.equal(JSON.parse(data['dungeon2-equipment-library-v1']).equipment.find(x=>x.name==='双触发装备').triggerEffects.length,1);
 create.click();named.get('name').value='独立debuff';named.get('startEnabled').checked=true;named.get('startSide').value='enemy';for(const fn of form.handlers.change||[])fn();named.get('startEnemyName').value='腐蚀';named.get('startDebuffType').value='dot';named.get('startDotDamage').value='125';
 for(const fn of form.handlers.change||[])fn();assert.equal(named.get('start-physicalVulnerability').disabled,true);assert.equal(named.get('startDotDamage').disabled,false);
 nodes.filter(n=>n.textContent==='＋ 添加开战效果').at(-1).click();named.get('startSide').value='enemy';for(const fn of form.handlers.change||[])fn();named.get('startEnemyName').value='罚罪';named.get('startDebuffType').value='healingReduction';named.get('start-healingReduction').value='20';for(const fn of form.handlers.change||[])fn();assert.equal(named.get('startDotDamage').disabled,true);
 await form.handlers.submit[0]({preventDefault(){}});const rows=JSON.parse(data['dungeon2-equipment-library-v1']).equipment.find(x=>x.name==='独立debuff').startingDebuffs.entries;assert.equal(rows.length,2);assert.equal(rows[0].type,'dot');assert.equal(rows[0].dotDamage,125);assert.equal(rows[0].physicalVulnerability,0);assert.equal(rows[1].type,'healingReduction');assert.equal(rows[1].healingReduction,20);assert.equal(rows[1].dotEnabled,false);
 nodes.filter(n=>n.tag==='button'&&n.textContent.startsWith('开战效果 2')).at(-1).click();assert.equal(named.get('startDebuffType').value,'healingReduction');assert.equal(named.get('start-healingReduction').value,20);nodes.filter(n=>n.textContent==='删除当前开战效果').at(-1).click();await form.handlers.submit[0]({preventDefault(){}});assert.equal(JSON.parse(data['dungeon2-equipment-library-v1']).equipment.find(x=>x.name==='独立debuff').startingDebuffs.entries.length,1);
 console.log('PASS: editor initialization, switching all effect panels, collecting fields, matrix values, local persistence, edit reload, independent duplicate');
})().catch(e=>{console.error(e);process.exitCode=1;});
