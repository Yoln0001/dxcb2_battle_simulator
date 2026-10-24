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
const calls=[];context.location.protocol='http:';context.fetch=async url=>{calls.push(url);return {ok:true,json:async()=>({schemaVersion:1,equipment:[]})};};
vm.createContext(context);
for(const file of ['wiki-details.js','editor.js','wiki-editor.js'])vm.runInContext(fs.readFileSync(root+'/frontend/js/equipment/'+file,'utf8'),context);
(async()=>{
 await new Promise(setImmediate);
 assert.equal(calls.filter(u=>u.startsWith('/api/wiki-equipment')).length,0);
 const before=calls.filter(u=>u.startsWith('/api/equipment/team')).length;
 context.window.customEquipmentEditor.render();context.window.customEquipmentEditor.render();
 assert.equal(calls.filter(u=>u.startsWith('/api/equipment/team')).length,before);
 picker.options.onExtra('__wiki__');await new Promise(setImmediate);
 assert.equal(calls.filter(u=>u.startsWith('/api/wiki-equipment')).length,1);
 picker.options.onExtra('__wiki__');await new Promise(setImmediate);
 assert.equal(calls.filter(u=>u.startsWith('/api/wiki-equipment')).length,1);
 assert.equal(calls.filter(u=>u.startsWith('/api/equipment/team')).length,before);
 console.log('PASS: encyclopedia makes zero startup requests, loads once on open, and list rerenders never reload team equipment');
})().catch(e=>{console.error(e);process.exitCode=1;});
