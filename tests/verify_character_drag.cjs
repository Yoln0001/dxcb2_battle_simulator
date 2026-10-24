const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
let changes=0,renumber=0,animation=0;
const classes=()=>{const values=new Set();return {values,add:k=>values.add(k),remove:k=>values.delete(k)};};
const container={handlers:{},classList:classes(),querySelectorAll(){return this.cards;},addEventListener(k,fn){this.handlers[k]=fn;},contains(value){return this.cards.includes(value);}};
function makeCard(id){const card={id,value:'saved-'+id,classList:classes(),closest(s){return s==='.character'?this:null;},getBoundingClientRect(){return {left:container.cards.indexOf(this)*100,top:0};},animate(){animation++;},before(c){container.cards.splice(container.cards.indexOf(c),1);container.cards.splice(container.cards.indexOf(this),0,c);},after(c){container.cards.splice(container.cards.indexOf(c),1);container.cards.splice(container.cards.indexOf(this)+1,0,c);}};card.head={closest(s){return s==='.card-head'?this:s==='.character'?card:null;}};return card;}
container.cards=[1,2,3,4].map(makeCard);const original=[...container.cards];
const context={document:{querySelector:()=>container},window:{matchMedia:()=>({matches:false})},updateCardPositions:()=>renumber++,dirty:()=>changes++};vm.createContext(context);vm.runInContext(fs.readFileSync(path.resolve(__dirname,'../frontend/js/ui/character-drag.js'),'utf8'),context);
const event=target=>({target,dataTransfer:{setData(){}},preventDefault(){this.prevented=true;}});
container.handlers.dragstart(event(original[0].head));assert(original[0].classList.values.has('character-dragging'));
container.handlers.dragover(event(original[2]));assert(original[2].classList.values.has('character-drop-target'));
container.handlers.drop(event(original[2]));assert.deepEqual(container.cards.map(c=>c.id),[2,3,1,4]);assert.equal(changes,1);assert.equal(renumber,1);assert(animation>0);assert.equal(original[0].value,'saved-1');assert(!original[0].classList.values.has('character-dragging'));assert(!original[2].classList.values.has('character-drop-target'));
container.handlers.dragstart(event(original[1].head));container.handlers.dragend();assert.equal(changes,1);assert(!container.classList.values.has('character-drag-active'));
const control={closest(s){return s==='.card-head'?original[0].head:s==='button,input,select,label,a'?this:null;}};container.handlers.pointerdown(event(control));assert.equal(original[0].head.draggable,false);container.handlers.pointerdown(event(original[0].head));assert.equal(original[0].head.draggable,true);
console.log('PASS: header dragging, drop target, animation, intact configuration, drag cancel and interactive controls');
