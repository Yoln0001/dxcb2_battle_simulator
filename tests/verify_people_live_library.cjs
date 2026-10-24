const assert=require('assert'),fs=require('fs'),vm=require('vm');
class N{constructor(tag){this.tag=tag;this.children=[];this.value='';this.textContent='';this.attrs={};}append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}setAttribute(k,v){this.attrs[k]=v;}addEventListener(){}showModal(){}close(){}dispatchEvent(){}}
const body=new N('body'),open=new N('button');let items=[{id:'p1',name:'夜魇人物',job:'夜魇',attributes:{speed:1000,magic:100}}];
const professions=[{name:'潜行者',jobs:['夜魇']},{name:'法师',jobs:['寒霜法师']}],window={showToast(){}};
const context={document:{body,createElement:t=>new N(t),querySelector:()=>open},SkillModel:{professions,findProfession:job=>professions.find(p=>p.name===job||p.jobs.includes(job))},window,structuredClone,Event:class{},fetch:async()=>({ok:true,json:async()=>({people:structuredClone(items)})})};
vm.runInNewContext(fs.readFileSync('frontend/js/people/library.js','utf8'),context);
(async()=>{const host=new N('div'),family=new N('select'),job=new N('select'),card={querySelector:s=>s.includes('profession')?family:job},sources={};let changes=0;
window.PeopleLibrary.attach(host,sources,card,()=>changes++);await open.onclick();const picker=host.children[0];picker.value='p1';picker.onchange();assert.equal(sources.day10.speed,1000);
items[0]={...items[0],name:'新名字',job:'寒霜法师',attributes:{speed:700,magic:1500}};await open.onclick();assert.equal(sources.selectedPerson.name,'新名字');assert.equal(sources.day10.magic,1500);assert.equal(family.value,'法师');assert.equal(job.value,'寒霜法师');assert.equal(changes,2);
items=[{...items[0],id:'copied-person',attributes:{speed:800,magic:1800}}];await open.onclick();assert.equal(sources.selectedPerson.id,'copied-person');assert.equal(sources.day10.speed,800);
items=[];await open.onclick();assert.equal(sources.selectedPerson,null);assert.equal(sources.day10.speed,0);assert.equal(picker.value,'');
console.log('PASS: person library updates name, profession, base attributes, copied selection and deletion in existing main-page roles');
})().catch(e=>{console.error(e);process.exitCode=1;});
