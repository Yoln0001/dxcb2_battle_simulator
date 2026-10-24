const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto'),path=require('path');
const root=path.resolve(__dirname,'..'),nodes=[];
class Node{constructor(tag){this.tag=tag;this.children=[];this.handlers={};this.value='';this.attributes={};this.classList={toggle(){},add(){}};nodes.push(this);}contains(target){return this===target||this.children.some(child=>child.contains(target));}querySelectorAll(selector){const all=this.children.flatMap(c=>[c,...c.querySelectorAll('*')]);return selector==='*'?all:all.filter(n=>n.className===selector.slice(1));}prepend(...items){this.children.unshift(...items);}get options(){return this.children;}after(){}append(...items){this.children.push(...items);}replaceChildren(...items){this.children=items;}setAttribute(k,v){this.attributes[k]=v;}addEventListener(k,fn){(this.handlers[k]??=[]).push(fn);}reportValidity(){return true;}showModal(){}close(){}click(){for(const fn of this.handlers.click||[])fn();}}
const open=new Node('button'),storage={'dungeon2-skill-library-v1':JSON.stringify({skills:[{id:'ice',name:'冰锥',damageType:'magic',job:'寒霜法师'},{id:'heal',name:'静气凝神',damageType:'none',job:'寒霜法师'},{id:'other',name:'其他',job:'夜魇'}]})};storage['dungeon2-equipment-library-v1']=JSON.stringify({equipment:[{id:'staff',name:'世界树之杖',triggerEnabled:true,triggerEffects:[{name:'魔力增幅',triggerType:'magic',effect:{kind:'amplify'}},{name:'回复增幅',triggerType:'none',effect:{kind:'amplify'}},{name:'物理增幅',triggerType:'physical',effect:{kind:'amplify'}}]}]});let published;const alerts=[];
const context={document:{body:new Node('body'),createElement:t=>new Node(t),querySelector:()=>open},location:{protocol:'file:'},SkillModel:require(root+'/frontend/js/skills/model.js'),window:{showToast:message=>alerts.push(message),onSkillGroupLibraryChange:g=>published=g},localStorage:{getItem:k=>storage[k]||null,setItem:(k,v)=>storage[k]=v},crypto,structuredClone,confirm:()=>true,console};

context.location.protocol='http:';
const defs=JSON.parse(storage['dungeon2-skill-library-v1']).skills;defs.find(s=>s.id==='heal').effect={kind:'buff',type:'regeneration'};defs.find(s=>s.id==='heal').healingRecipient='self';
let savedGroups=[];
context.fetch=async(url,options)=>{let value;
 if(url==='/api/library-sets/bosses')value={libraries:[{id:'map52',name:'图52'}]};
 else if(url.startsWith('/api/bosses'))value={bosses:url.includes('map52')?[{id:'phantom',name:'圣者的幻影',skillGroup:{skills:[{id:'extract',name:'生命萃取',effect:{kind:'debuff',type:'lifeLoss'}}]}}]:[]};
 else if(url==='/api/skills')value={skills:defs};
 else if(url==='/api/equipment')value=JSON.parse(storage['dungeon2-equipment-library-v1']);
 else if(options.method==='POST'||options.method==='PUT'){const g=JSON.parse(options.body);savedGroups=[g];value={groups:savedGroups,item:g};}
 else value={groups:savedGroups};
 return {ok:true,json:async()=>structuredClone(value)};
};
vm.createContext(context);vm.runInContext(fs.readFileSync(root+'/frontend/js/skill-groups/editor.js','utf8'),context);
(async()=>{
 await new Promise(r=>setTimeout(r,10));
 const byLabel=label=>nodes.filter(n=>n.attributes['aria-label']===label).at(-1);
 const change=async(n,value)=>{n.value=value;for(const fn of n.handlers.change||[])await fn();};
 assert.equal(byLabel('技能适用范围').value,'general');
 await change(byLabel('筛选技能组职业大类'),'法师');await change(byLabel('筛选技能组转职'),'寒霜法师');nodes.find(n=>n.textContent==='＋ 创建技能组').click();byLabel('技能组名称').value='图52圣者专用';
 await change(byLabel('技能适用范围'),'boss');await change(byLabel('适用Boss库'),'map52');await change(byLabel('适用Boss'),'phantom');
 await change(byLabel('子技能组1子技能组类型'),'yes');await change(byLabel('子技能组1条件1类型'),'memberStatus');
 const negative=byLabel('子技能组1条件1指定负面');assert.equal(negative.options.length,2);negative.value=negative.options[1].value;
 const positive=byLabel('子技能组1条件1指定增益');assert.equal(positive.options.length,2);positive.value=positive.options[1].value;
 await change(byLabel('子技能组1条件1技能'),'heal');byLabel('子技能组1else技能').value='ice';
 assert.equal(byLabel('子技能组1条件1技能释放对象').disabled,false);assert.equal(byLabel('子技能组1条件1技能释放对象').value,'matchedMember');
 byLabel('子技能组1条件1状态识别延迟').value='0.3';byLabel('子技能组1条件1操作耗时').value='0.5';
 const jump=byLabel('子技能组1结束后跳转到');jump.value=jump.options[1].value;
 const form=nodes.find(n=>n.tag==='form');await form.handlers.submit[0]({preventDefault(){}});
 assert.equal(savedGroups.length,1,alerts.join(';'));
 const g=savedGroups[0],c=g.subgroups[0].skills[0].decision.cases[0];assert.equal(g.scope.kind,'boss');assert.equal(g.scope.libraryId,'map52');assert.equal(g.scope.bossId,'phantom');assert.equal(g.scope.bossName,'圣者的幻影');
 assert.equal(c.recognitionDelay,.3);assert.equal(c.operationDelay,.5);assert.equal(byLabel('子技能组1条件1状态识别延迟').value,.3);assert.equal(byLabel('子技能组1条件1操作耗时').value,.5);assert.equal(c.kind,'memberStatus');assert.equal(c.includeSelf,true);assert.equal(c.requiredDebuff.type,'lifeLoss');assert.equal(c.absentBuff.skillId,'heal');assert.equal(c.targetSelection,'matchedMember');assert.equal(g.subgroups[0].nextGroup,g.subgroups[0].id);
 assert.equal(byLabel('适用Boss').value,'phantom');assert.equal(byLabel('子技能组1条件1技能释放对象').value,'matchedMember');assert(byLabel('已保存的技能组').options.some(o=>o.textContent.includes('圣者的幻影专用')));
 console.log('PASS: scenario selection, Boss-derived effects, same-member condition, targeted heal and save/reload');
})().catch(e=>{console.error(e);process.exitCode=1;});
