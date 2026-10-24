const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const source=fs.readFileSync(path.resolve(__dirname,'../frontend/js/app.js'),'utf8');
let dirtyCount=0;
const container={cards:[],querySelectorAll(){return this.cards;}};
function card(id){const number={},title={},enabled={setAttribute(k,v){this[k]=v;}},buttons=[-1,1].map(direction=>({dataset:{direction},setAttribute(k,v){this[k]=v;}}));return {id,dataset:{},stats:{magic:id*100},equipment:{weapon:'weapon'+id},skillGroup:{value:'group'+id,dataset:{pendingGroup:'pending'+id}},querySelector(s){return s.includes('.number')?number:s.includes('strong')?title:enabled;},querySelectorAll(){return buttons;},number,title,buttons,before(c){container.cards.splice(container.cards.indexOf(c),1);container.cards.splice(container.cards.indexOf(this),0,c);},after(c){container.cards.splice(container.cards.indexOf(c),1);container.cards.splice(container.cards.indexOf(this)+1,0,c);}};}
const original=[1,2,3,4].map(card);container.cards=[...original];
const context=vm.createContext({$:()=>container,dirty:()=>dirtyCount++});
vm.runInContext(source.slice(source.indexOf('function updateCardPositions()'),source.indexOf('function updateCount()')),context);
context.card=original[0];vm.runInContext('updateCardPositions();moveCharacterCard(card,1)',context);
assert.deepEqual(container.cards.map(c=>c.id),[2,1,3,4]);assert.equal(dirtyCount,1);
assert.strictEqual(container.cards[1],original[0]);assert.equal(container.cards[1].skillGroup.dataset.pendingGroup,'pending1');assert.equal(container.cards[1].equipment.weapon,'weapon1');
assert.equal(container.cards[0].number.textContent,'01');assert.equal(container.cards[1].title.textContent,'角色 2');assert(container.cards[0].buttons[0].disabled);assert(container.cards[3].buttons[1].disabled);
context.card=original[3];vm.runInContext('moveCharacterCard(card,-1)',context);assert.deepEqual(container.cards.map(c=>c.id),[2,1,4,3]);
context.card=container.cards[0];vm.runInContext('moveCharacterCard(card,-1)',context);assert.equal(dirtyCount,2);
assert(container.cards.every((c,i)=>c.dataset.index===i));
console.log('PASS: card moves swap party positions, preserve all existing controls and pending selections, update numbers and boundary buttons');
