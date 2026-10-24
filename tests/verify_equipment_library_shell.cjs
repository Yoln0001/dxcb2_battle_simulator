const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const root=process.argv[2]||require("path").resolve(__dirname,"..");const model=require(root+'/frontend/js/equipment/model.js');
const nodes=[],named=new Map();
class Node{
 constructor(tag){this.tag=tag;this.children=[];this.handlers={};this.dataset={};this.classList={add(){},remove(){},toggle(){}};this.checked=false;this.defaultValue='';this.value='';this.textContent='';nodes.push(this);}
 set name(n){this._name=n;named.set(n,this);}get name(){return this._name;}
 get firstChild(){return this.children[0];}after(){} get lastChild(){return this.children.at(-1);}append(...children){this.children.push(...children);}replaceChildren(...children){this.children=children;}
 setAttribute(k,v){this[k]=v;}addEventListener(kind,fn){(this.handlers[kind]??=[]).push(fn);}querySelectorAll(selector){const all=this.children.flatMap(c=>[c,...c.querySelectorAll('*')]);return selector==='[data-matrix]'?all.filter(c=>c.dataset.matrix):all;}
 get elements(){return {namedItem:n=>named.get(n)};}reportValidity(){return true;}
 reset(){for(const x of named.values()){x.checked=false;x.value=x.tag==='select'?(x.children[0]?.value||''):x.defaultValue;}}
 close(){}showModal(){}click(){for(const fn of this.handlers.click||[])fn();}
}
const toast=new Node('div'),open=new Node('button'),data={};
let picker;const context={document:{createElement:tag=>new Node(tag),body:new Node('body'),querySelector:s=>s==='#toast'?toast:open},window:{PlayerLibraries:{current:{},mount(host,kind,label,onSwitch,options){picker={onSwitch,options};const select=new Node('select');host.append(select);return select;}},showToast(){},EquipmentModel:model,SkillModel:require(root+'/frontend/js/skills/model.js')},location:{protocol:'file:'},localStorage:{getItem:k=>data[k]??null,setItem:(k,v)=>data[k]=v},setTimeout:()=>0,clearTimeout(){},confirm:()=>true,crypto,console,structuredClone};
vm.createContext(context);
for(const file of ['wiki-details.js','editor.js','wiki-editor.js'])vm.runInContext(fs.readFileSync(root+'/frontend/js/equipment/'+file,'utf8'),context);
const shell=nodes.find(n=>n.id==='equipment-library-dialog');assert.ok(shell);
const panels=shell.children.slice(2);assert.equal(panels.length,2);assert.equal(panels[0].hidden,false);assert.equal(panels[1].hidden,true);
const tabs=shell.children[1].children;assert.equal(tabs[0].tag,'select');assert.equal(picker.options.extraOptions[0].name,'百科装备库');picker.options.onExtra('__wiki__');assert.equal(panels[0].hidden,true);assert.equal(panels[1].hidden,false);
assert.ok(nodes.find(n=>n.id==='equipment-form'));assert.ok(nodes.find(n=>n.id==='wiki-equipment-form'));
assert.ok(nodes.filter(n=>n['aria-label']==='武威最小').length>=2);
console.log('PASS: unified equipment dialog, switching libraries, base attributes in both editors');

for(const label of ['战斗开始效果','施加阵营','特效类型','物理易伤 %','魔法易伤 %'])assert.ok(nodes.filter(n=>n['aria-label']===label).length>=2);
assert(!nodes.some(n=>n['aria-label']==='物理易伤固定值'));
const legacy=model.blank();Object.assign(legacy,{id:'old',name:'old',baseAttributes:{physicalVulnerability:{value:12},magicVulnerability:{value:18}}});const migrated=model.validate(legacy);assert.equal(migrated.startingDebuffs.physicalVulnerability,12);assert.equal(migrated.startingDebuffs.enabled,true);assert(!('physicalVulnerability' in migrated.baseAttributes));
