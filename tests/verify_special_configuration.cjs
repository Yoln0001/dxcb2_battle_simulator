const assert=require('assert'),M=require('../frontend/js/configurations/special.js');
const s=M.blank();s.day10={magic:1000,strength:200};s.contract.magic=10;s.stone.magic=20;s.holy.magic=100;s.ring={magic:50,magicDamage:8};s.trophies={magic:30,magicDamage:7,hitRate:5};s.saturation={weapon:{magic:25,weaponPower:60}};
const gear=[{id:'e',name:'杖',baseAttributes:{magic:{min:100,max:300},weaponPower:{min:10,max:20},magicDamage:{value:12},hitRate:{value:-4}},crystal:{enabled:true,attributes:{magic:5}}}];
const value=M.calculate(s,{weapon:'e'},gear,['magic','strength','weaponPower','magicDamage','hitRate']);assert.equal(value.stats.magic,(1700*1.25+100+150)*1.3);assert.equal(value.stats.weaponPower,16);assert.equal(value.stats.magicDamage,19);assert.equal(value.stats.hitRate,1);assert.equal(value.stats.strength,340);
const clone=structuredClone(s);clone.saturation.weapon.magic=101;assert.throws(()=>M.calculate(clone,{weapon:'e'},gear,['magic']));assert.throws(()=>M.calculate(s,{weapon:'missing'},gear,['magic']));
console.log('PASS: day150 base, saturation, crystal, additive sources, final trophy multiplier, other flat stats and invalid values');

class N{constructor(tag){this.tag=tag;this.children=[];this.handlers={};this.value='';}append(...n){this.children.push(...n);}replaceChildren(...n){this.children=n;}setAttribute(k,v){this[k]=v;}addEventListener(k,fn){this.handlers[k]=fn;}}
global.document={createElement:t=>new N(t)};const nodes=new Map(),body=new N('div'),panel=new N('div');for(const key of ['magic','strength','weaponPower','physicalDamage','dotDamage','magicDamage','hitRate',...M.imprintKeys,...M.five]){const input=new N('input');input.name=key;nodes.set(key,input);panel.append(input);}const weapon=new N('select');weapon.value='e';const armorSelect=new N('select');armorSelect.value='a';gear.push({id:'a',name:'防具',baseAttributes:{armor:{min:10,max:20}}});const card={querySelector(selector){if(selector==='.card-body')return body;if(selector==='.stats')return panel;if(selector==='.equipment select[name="weapon"]')return weapon;if(selector==='.equipment select[name="armor"]')return armorSelect;const match=selector.match(/name="([^"]+)"/);return nodes.get(match?.[1])||panel.children.flatMap(n=>[n,...n.children]).find(n=>n.name===match?.[1]);},querySelectorAll(selector){return selector==='.stats input'?panel.children.flatMap(n=>n.tag==='input'?[n]:n.children.filter(x=>x.tag==='input')):[weapon];}};let changes=0;
M.attach({card,sources:s,fields:[['magic','魔力',0],['strength','力量',0],['technique','技巧',0],['speed','速度',0],['constitution','体质',0],['weaponPower','武威',0],['physicalDamage','物理伤害 %',0],['dotDamage','持续伤害 %',0],['magicDamage','魔法伤害 %',0],['hitRate','命中 %',0],...M.imprintKeys.filter(k=>!['hitRate','magicDamage'].includes(k)).map(k=>[k,k+' %',0])],slots:[['weapon','武器'],['armor','防具']],getLibrary:()=>gear,onChange:()=>changes++});
assert.equal(card.specialError,'');assert.equal(card.querySelector('.stats [name="armor"]').value,20);assert.equal(nodes.get('magic').value,3088);assert.ok(card.querySelectorAll('.stats input').every(n=>n.readOnly));assert.ok(card.querySelector('.stats [name="armor"]'));
const walk=n=>[n,...n.children.flatMap(walk)],inputs=walk(body).filter(n=>n.tag==='input');const dayMagic=inputs.find(n=>n['aria-label']==='魔力');dayMagic.value='2000';dayMagic.handlers.input();assert.equal(nodes.get('magic').value,Math.round((3400*1.25+100+150)*1.3));assert.equal(card.specialSources.day10.magic,2000);assert.equal(changes,1);
const rate=inputs.find(n=>n['aria-label']==='魔力饱和度');rate.value='50';rate.handlers.input();assert.equal(nodes.get('magic').value,Math.round((3400*1.25+100+200)*1.3));assert.equal(card.specialSources.saturation.weapon.magic,50);
console.log('PASS: readonly panel, source input and saturation changes recalculate immediately');

assert.deepEqual(M.holyFor('法师'),{strength:0,magic:1560,technique:1560,speed:0,constitution:680});assert.equal(M.holyFor('战士').constitution,1360);assert.equal(M.holyFor('野蛮人').strength,1560);

const stoneHit=M.blank();stoneHit.stone.hitRate=12.5;stoneHit.trophies.hitRate=8;assert.equal(M.calculate(stoneHit,{},[],['hitRate']).stats.hitRate,20.5);

assert.equal(M.imprintFor('法师','寒霜法师').finalMagicDamage,8);assert.equal(M.imprintFor('战士','剑魔').finalPhysicalDamage,6);assert.equal(M.imprintFor('潜行者','幻术刺客').finalPhysicalDamage,9);assert.equal(M.imprintFor('野蛮人','毁灭者').hitRate,8);

const lifeKeys=['physicalSingleLifesteal','physicalAreaLifesteal','magicSingleLifesteal','magicAreaLifesteal'];const life=M.calculate(M.blank(),{weapon:'v'},[{id:'v',baseAttributes:{lifesteal:{value:5}}}],lifeKeys).stats;assert.ok(lifeKeys.every(k=>life[k]===5));

assert.equal(nodes.get('magic').value,Math.round((3400*1.25+100+200)*1.3));assert.equal(Number(nodes.get('magic').dataset.calculatedValue),Number(((3400*1.25+100+200)*1.3).toFixed(8)));

const exact=structuredClone(s);exact.saturation.weapon.magic={mode:'value',value:200};assert.equal(M.calculate(exact,{weapon:'e'},gear,['magic']).stats.magic,(1700*1.25+100+200)*1.3);for(const n of [99,301,NaN]){exact.saturation.weapon.magic.value=n;assert.throws(()=>M.calculate(exact,{weapon:'e'},gear,['magic']));}
let mode=walk(body).find(n=>n['aria-label']==='装备属性使用百分比');mode.checked=false;mode.handlers.change();assert.deepEqual(card.specialSources.saturation.weapon.magic,{mode:'value',value:200});const exactInput=walk(body).find(n=>n['aria-label']==='魔力数值');assert.equal(exactInput.min,100);assert.equal(exactInput.max,300);assert.ok(exactInput.readOnly);assert.ok(card.specialError.includes('未填写我的数值'));card.specialSources.saturation.weapon.magic={mode:'value',value:250};mode=walk(body).find(n=>n['aria-label']==='装备属性使用百分比');mode.checked=true;mode.handlers.change();assert.equal(card.specialSources.saturation.weapon.magic,75);
console.log('PASS: exact gear bounds, input mode conversion and immediate validation');

const trophies=M.blank();trophies.day10.magic=100;trophies.trophies.magic=5;trophies.selectedTrophies=[{name:'a',attributes:{magic:10,hitRate:3}},{name:'b',attributes:{magic:15,hitRate:2}}];const combined=M.calculate(trophies,{},[],['magic','hitRate']).stats;assert.equal(combined.magic,221);assert.equal(combined.hitRate,5);console.log('PASS: selected trophy bonuses combine with manual bonuses');

gear.push({id:'owned',name:'我的杖',baseAttributes:{magic:{min:100,max:300,ownedValue:180}}});assert.equal(M.calculate(M.blank(),{weapon:'owned'},gear,['magic']).stats.magic,180);weapon.value='owned';weapon.handlers.change();assert.equal(card.specialSources.saturation.weapon.magic,40);weapon.value='e';weapon.handlers.change();assert.equal(card.specialSources.saturation.weapon.magic,undefined);console.log('PASS: saved personal gear values reused and previous equipment overrides cleared');

const stored=M.blank();stored.gearPercentEnabled=false;stored.saturation.weapon={magic:{mode:'value',value:290}};assert.equal(M.calculate(stored,{weapon:'owned'},gear,['magic']).stats.magic,180);assert.throws(()=>M.calculate(stored,{weapon:'e'},gear,['magic']),/未填写我的数值/);console.log('PASS: percentage disabled uses library values and rejects missing personal values');

const defense=M.blank();defense.day10={armor:100,resistance:200};defense.trophies={armor:5};assert.deepEqual(M.calculate(defense,{armor:'a'},gear,['armor','resistance']).stats,{armor:195,resistance:340});console.log('PASS: day150 base armor/resistance multiply by 1.7, equipment bonuses remain additive');

const legacy=M.blank();legacy.day10.magic=100;legacy.contract.magic=99;legacy.ring={magic:999,magicDamage:88};
assert.equal(M.calculate(legacy,{},[],['magic','magicDamage']).stats.magic,170);
assert.equal(M.calculate(legacy,{},[],['magic','magicDamage']).stats.magicDamage,0);
legacy.selectedContract={category:'magic',baseBonus:12};legacy.selectedRing={mainAttribute:'magic',mainValue:750,secondaryAttribute:'constitution',secondaryValue:500};
assert.equal(M.calculate(legacy,{},[],['magic']).stats.magic,940.4);
legacy.selectedContract=null;legacy.selectedRing=null;assert.equal(M.calculate(legacy,{},[],['magic']).stats.magic,170);
console.log('PASS: old manual contract/ring bonuses never stack with selected wear; removing wear restores baseline');

const ringSource=M.blank();ringSource.selectedRing={mainAttribute:'technique',mainValue:750,secondaryAttribute:'speed',secondaryValue:500,gain:'physicalMagicDamage',gainValue:13,restriction:'none'};
const ringPreview=M.calculate(ringSource,{},[],['physicalDamage','magicDamage','technique']);assert.deepEqual(ringPreview.ringPanelBonuses,{});let ringPanel=ringPreview.stats;assert.equal(ringPanel.physicalDamage,0);assert.equal(ringPanel.magicDamage,0);assert.equal(ringPanel.technique,750);
ringSource.selectedRing.restriction='twoEnemies';assert.equal(M.calculate(ringSource,{},[],['magicDamage']).stats.magicDamage,0);assert.equal(M.calculate(ringSource,{},[],['magicDamage'],{enemyCount:2}).stats.magicDamage,0);
ringSource.selectedRing.restriction='missingParty';assert.equal(M.calculate(ringSource,{},[],['magicDamage'],{partySize:2}).stats.magicDamage,0);
ringSource.selectedRing.gain='doubleBlock';ringSource.selectedRing.restriction='fullHealth';ringPanel=M.calculate(ringSource,{},[],['physicalBlock','magicBlock']).stats;assert.equal(ringPanel.physicalBlock,0);assert.equal(ringPanel.magicBlock,0);
ringSource.selectedRing=null;assert.equal(M.calculate(ringSource,{},[],['magicDamage']).stats.magicDamage,0);
console.log('PASS: ring panel gains, dual damage, restrictions, missing-party stacks, block and removal');

// Failed recalculation must invalidate the old panel and expose the missing-value error.
card.specialSources.gearPercentEnabled=false;weapon.value='e';card.refreshSpecial();
assert.ok(card.specialError.includes('未填写我的数值'));
assert.ok(card.querySelectorAll('.stats input').every(n=>n.value===''));
assert.equal(nodes.get('magic').dataset.calculatedValue,undefined);
const notice=walk(body).find(n=>n.className==='character-panel-error');
assert.equal(notice.hidden,false);assert.ok(notice.textContent.includes('未填写我的数值'));
for(const a of Object.values(gear[0].baseAttributes))if(a.min!==a.max)a.ownedValue=a.min;
gear[1].baseAttributes.armor.ownedValue=10;
card.refreshSpecial();assert.equal(card.specialError,'');assert.equal(notice.hidden,true);assert.notEqual(nodes.get('magic').value,'');assert.ok(Number.isFinite(Number(nodes.get('magic').dataset.calculatedValue)));
console.log('PASS: failed calculation clears stale panel, shows missing-value notice and recovers after library values are filled');
