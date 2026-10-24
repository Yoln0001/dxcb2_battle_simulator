const assert=require('assert'),fs=require('fs'),vm=require('vm');
const M=require('../frontend/js/configurations/special.js');
class Node {
 constructor(tag){this.tag=tag;this.children=[];this.value='';this.style={};}
 append(...nodes){this.children.push(...nodes);}
 after(){}
 replaceChildren(...nodes){this.children=nodes;}
 setAttribute(k,v){this[k]=v;}
 addEventListener(){}
 setCustomValidity(){}
 reportValidity(){return true;}
}
(async()=>{
 const document={body:new Node('body'),createElement:t=>new Node(t),querySelector:()=>new Node('button')};
 const current={holies:'a',imprints:'a'},reload={},pending=[];
 let revision=0;
 const rows=(kind,library)=>kind==='holies'?[{id:library+'h',name:'战士圣迹',kind:'战士',attributes:{strength:library==='a'?100+revision:200}}]:[
 {id:library+'b',name:'战士辉印',kind:'战士',scope:'base',job:'战士',attributes:{finalPhysicalDamage:library==='a'?4+revision:8}},
 {id:library+'e',name:'剑魔额外辉印',kind:'战士',scope:'extra',job:'剑魔',attributes:{finalPhysicalDamage:library==='a'?3:5}},
 {id:library+'m',name:'法师辉印',kind:'法师',scope:'base',job:'法师',attributes:{finalMagicDamage:11}}];
 const window={PlayerLibraries:{current,mount:(_,kind,__,callback)=>reload[kind]=callback},showToast:e=>{throw Error(e)},SpecialConfiguration:M};
 let delay=false;
 const context=vm.createContext({document,window,structuredClone,fetch:async url=>{
  const kind=url.includes('/holies')?'holies':'imprints',library=new URL('http://local'+url).searchParams.get('library');
  const data={[kind]:rows(kind,library)};
  if(delay)await new Promise(resolve=>pending.push(resolve));
  return {ok:true,json:async()=>data};
 }});
 for(const kind of ['holies','imprints'])vm.runInContext(fs.readFileSync('frontend/js/'+kind+'/library.js','utf8'),context);
 const {execFileSync}=require('child_process');
 const cases=JSON.parse(execFileSync('venv/Scripts/python.exe',['-c',"import json;from backend.api.holies import TYPES,HOLY_LEVELS,level_attributes;print(json.dumps([[k,h,o,level_attributes(k,h,o)] for k in TYPES for h in HOLY_LEVELS for o in [0,1,6,29,30,31,599,600,601]]))"],{encoding:'utf8'}));
 for(const [kind,h,o,expected] of cases)assert.deepEqual(JSON.parse(JSON.stringify(window.HolyLibrary.levelAttributes(kind,h,o))),expected);
 console.log('PASS: frontend/backend holy tables and solar cycle agree for all six professions and level boundaries');
 const source=M.blank();source.holy={strength:9999};source.imprint={finalPhysicalDamage:99};
 source.selectedHoly={id:'old',kind:'战士',attributes:{strength:9999}};
 let updates=0,profession='战士',job='剑魔';
 function recalculate(){window.HolyLibrary.resolve(source,profession);window.ImprintLibrary.resolve(source,profession,job);updates++;}
 for(const library of [window.HolyLibrary,window.ImprintLibrary])library.attach(new Node('div'),source,recalculate);
 await new Promise(setImmediate);recalculate();
 function stats(){return M.calculate(source,{},[],['strength','finalPhysicalDamage','finalMagicDamage']).stats;}
 assert.equal(stats().strength,100);assert.equal(stats().finalPhysicalDamage,7);
 assert.equal(source.selectedHoly.id,'ah');assert.equal(source.selectedExtraImprint.id,'ae');
 const before=updates;revision=2;await reload.holies();await reload.imprints();
 assert(updates>before);assert.equal(stats().strength,102);assert.equal(stats().finalPhysicalDamage,9);
 current.holies='b';current.imprints='b';assert(!window.HolyLibrary.isReady());
 await reload.holies();await reload.imprints();assert.equal(stats().strength,200);assert.equal(stats().finalPhysicalDamage,13);
 assert.equal(source.selectedImprint.id,'bb');assert.equal(source.selectedExtraImprint.id,'be');
 profession='法师';job='法师';recalculate();assert.equal(stats().strength,0);assert.equal(stats().finalPhysicalDamage,0);assert.equal(stats().finalMagicDamage,11);assert.equal(source.selectedExtraImprint,null);
 // A late response from the previous library must not overwrite the current library.
 delay=true;current.holies='a';const stale=reload.holies();current.holies='b';const fresh=reload.holies();
 pending[1]();await fresh;pending[0]();await stale;profession='战士';recalculate();assert.equal(stats().strength,200);
 console.log('PASS: current holy/imprint libraries, base plus extra, save refresh, profession changes, stale snapshots and out-of-order responses');
})().catch(e=>{console.error(e);process.exitCode=1;});
