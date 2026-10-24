 'use strict';
(()=>{
 const container=document.querySelector('#characters');
 let source=null,target=null;
 const cards=()=>[...container.querySelectorAll('.character')];
 const reducedMotion=()=>window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
 window.CharacterCardMotion={capture(items){
  if(reducedMotion())return ()=>{};
  const before=new Map(items.map(card=>[card,card.getBoundingClientRect()]));
  return ()=>{for(const card of items){const old=before.get(card),now=card.getBoundingClientRect();const x=old.left-now.left,y=old.top-now.top;
   if((x||y)&&card.animate)card.animate([{transform:`translate(${x}px,${y}px)`},{transform:'translate(0,0)'}],{duration:260,easing:'cubic-bezier(.2,.8,.2,1)'});
  }};
 }};
 function clear(){source?.classList.remove('character-dragging');target?.classList.remove('character-drop-target');container.classList.remove('character-drag-active');source=null;target=null;}
 container.addEventListener('pointerdown',event=>{const head=event.target.closest('.card-head');if(head)head.draggable=!event.target.closest('button,input,select,label,a');});
 container.addEventListener('dragstart',event=>{
  const head=event.target.closest('.card-head');
  if(!head||event.target.closest('button,input,select,label,a')){event.preventDefault();return;}
  source=head.closest('.character');source.classList.add('character-dragging');container.classList.add('character-drag-active');
  event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain','character-position');
 });
 container.addEventListener('dragover',event=>{
  if(!source)return;event.preventDefault();event.dataTransfer.dropEffect='move';
  const next=event.target.closest('.character');
  if(target!==next){target?.classList.remove('character-drop-target');target=next&&next!==source?next:null;target?.classList.add('character-drop-target');}
 });
 container.addEventListener('dragleave',event=>{if(source&&!container.contains(event.relatedTarget)){target?.classList.remove('character-drop-target');target=null;}});
 container.addEventListener('drop',event=>{
  if(!source)return;event.preventDefault();const destination=event.target.closest('.character'),moving=source;
  const order=cards(),from=order.indexOf(moving),to=order.indexOf(destination);clear();
  if(from<0||to<0||from===to)return;
  const finish=window.CharacterCardMotion.capture(order);
  if(from<to)destination.after(moving);else destination.before(moving);
  updateCardPositions();dirty();finish();
 });
 container.addEventListener('dragend',clear);
})();
