const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('frontend/js/app.js','utf8');
const gear=[{id:'mage',name:'霜语',category:'weapon',weaponJob:'法师'},{id:'rogue',name:'匕首',category:'weapon',weaponJob:'潜行者'},{id:'shared',name:'通用',category:'weapon',weaponJob:''},{id:'armor',name:'法袍',category:'armor',weaponJob:''}];
const job={value:'夜魇'},profession={value:'潜行者'};
const card={querySelector:s=>s.includes('profession')?profession:job};
const context=vm.createContext({teamEquipmentLibrary:gear,slots:[['weapon','武器'],['armor','防具']],window:{SkillModel:{findProfession:j=>j==='夜魇'?{name:'潜行者'}:j==='寒霜法师'?{name:'法师'}:null}},document:{createElement:()=>({})}});
vm.runInContext(source.slice(source.indexOf('const slotCategory='),source.indexOf('function updateEquipmentOptions(')),context);
function select(name,value){return {name,value,children:[],replaceChildren(){this.children=[]},append(x){this.children.push(x)}};}
function fill(name,value){const s=select(name,value);context.s=s;context.card=card;vm.runInContext('fillEquipmentOptions(s,card)',context);return s;}
assert.equal(fill('weapon','mage').value,'');assert.equal(fill('weapon','rogue').value,'rogue');assert.equal(fill('weapon','shared').value,'shared');assert.equal(fill('armor','armor').value,'armor');
job.value='';assert.equal(fill('weapon','rogue').value,'rogue');assert.equal(fill('weapon','mage').value,'');
job.value='寒霜法师';profession.value='法师';assert.equal(fill('weapon','mage').value,'mage');assert.equal(fill('weapon','rogue').value,'');
assert.equal(fill('weapon','missing').value,'missing');
console.log('PASS: profession change clears incompatible weapon, preserves compatible/common gear and handles intermediate job update');
