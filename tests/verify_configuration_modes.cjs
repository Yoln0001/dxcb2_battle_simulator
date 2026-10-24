const fs=require('fs'),vm=require('vm'),assert=require('assert');
const nodes={};function node(){return{hidden:false,readOnly:false,disabled:false,attrs:{},classList:{toggle(){}},setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,fn){this[k]=fn;}};}
for(const id of ['#mode-regular','#mode-special','#configuration-mode-help','#boss-target-picker'])nodes[id]=node();
const number={...node(),tagName:'INPUT',type:'number'},race={...node(),tagName:'SELECT'},immune={...node(),tagName:'INPUT',type:'checkbox'};nodes['#target-fields']={querySelectorAll:()=>[number,race,immune]};let actual={configurationType:'regular',value:42};
const ctx={document:{body:{dataset:{}}},configurationType:'regular',modeDrafts:{},$:id=>nodes[id],structuredClone,collect:()=>structuredClone(actual),apply(data){actual=structuredClone(data);ctx.configurationType=data.configurationType;ctx.syncConfigurationMode();},dirty(){},window:{BossLibrary:{setMode(s){this.special=s;}},newTeamConfiguration:type=>({configurationType:type,value:0})}};
vm.createContext(ctx);const code=fs.readFileSync('frontend/js/app.js','utf8');vm.runInContext(code.slice(code.indexOf('function syncConfigurationMode()')),ctx);
assert.equal(nodes['#boss-target-picker'].hidden,true);assert.equal(number.readOnly,false);
ctx.window.switchConfigurationMode('special');assert.equal(actual.configurationType,'special');assert.equal(number.readOnly,true);assert(race.disabled&&immune.disabled);assert.equal(nodes['#boss-target-picker'].hidden,false);actual.value=99;
ctx.window.switchConfigurationMode('regular');assert.equal(actual.value,42);assert.equal(number.readOnly,false);assert.equal(race.disabled,false);
ctx.window.switchConfigurationMode('special');assert.equal(actual.value,99);assert.equal(nodes['#mode-special'].attrs['aria-pressed'],'true');assert(ctx.window.BossLibrary.special);
console.log('PASS: mode buttons, independent drafts, regular manual inputs and special readonly Boss fields');
