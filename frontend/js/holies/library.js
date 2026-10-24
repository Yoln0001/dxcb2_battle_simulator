"use strict";
(()=>{
 const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 const attrs=[["strength", "力量"], ["magic", "魔力"], ["technique", "技巧"], ["speed", "速度"], ["constitution", "体质"]];
 const types=['战士','法师','潜行者','火枪手','圣职','野蛮人'];const blank=()=>({name:'',kind:types[0],attributes:Object.fromEntries(attrs.map(([k])=>[k,0]))});let items=[],selected='',draft=blank();const subscribers=new Set();let loadedLibrary=null;const currentLibrary=()=>window.PlayerLibraries?.current.holies||'';
 const dialog=el('dialog');dialog.id='holies-library';dialog.className='configuration-dialog';const heading=el('div');heading.className='configuration-heading';heading.append(el('h2','圣迹库'));const close=el('button','×');close.type='button';close.onclick=()=>dialog.close();heading.append(close);dialog.append(heading);const overview=el('section');overview.className='holy-overview';dialog.append(overview);const layout=el('div');layout.className='trophy-layout';const sidebar=el('div'),form=el('form');layout.append(sidebar,form);dialog.append(layout);document.body.append(dialog);
 const list=el('div');list.className='trophy-list-results';
 const holyLevels={20:[10,20],30:[21,42],40:[36,72],50:[55,110],60:[82,162],70:[115,230],80:[158,316],90:[214,428],100:[280,560]};
 const weights={'战士':{strength:1,technique:1,speed:1,constitution:2},'野蛮人':{strength:2,speed:2,constitution:1},'火枪手':{strength:1,technique:2,speed:1,constitution:1},'潜行者':{technique:2,speed:2,constitution:1},'法师':{magic:2,technique:2,constitution:1},'圣职':{magic:2,technique:1,constitution:2}};
 const cycle=[['圣职','technique',20],['法师','magic',30],['野蛮人','strength',30],['战士','constitution',20],['潜行者','technique',30],['火枪手','technique',30],['圣职','magic',30],['法师','technique',30],['野蛮人','technique',20],['战士','strength',30],['潜行者','speed',30],['火枪手','strength',30],['圣职','technique',20],['法师','magic',20],['野蛮人','strength',20],['战士','constitution',20],['潜行者','strength',20],['火枪手','constitution',20],['圣职','magic',20],['法师','constitution',20],['野蛮人','constitution',20],['战士','technique',30],['潜行者','technique',20],['火枪手','technique',20],['圣职','constitution',30],['法师','technique',20],['野蛮人','speed',30],['战士','speed',20],['潜行者','constitution',20],['火枪手','speed',20]];
 function levelAttributes(kind,holyLevel,obeliskLevel){
  const values=holyLevels[holyLevel];if(!values||!Number.isSafeInteger(obeliskLevel)||obeliskLevel<0)return null;
  const holy=Object.fromEntries(attrs.map(([k])=>[k,weights[kind]?.[k]?values[weights[kind][k]-1]:0]));
  const obelisk=Object.fromEntries(attrs.map(([k])=>[k,0]));const cycles=Math.floor(obeliskLevel/30),remainder=obeliskLevel%30;
  cycle.forEach(([family,k,value],index)=>{if(family===kind)obelisk[k]+=value*(cycles+Number(index<remainder));});
  return {holy,obelisk,total:Object.fromEntries(attrs.map(([k])=>[k,holy[k]+obelisk[k]]))};
 }
 async function request(path='',method='GET',body){if(window.AppRequests)await window.AppRequests.ready;const library=currentLibrary();const r=await (window.AppRequests?.fetch||fetch)('/api/holies'+path+(window.PlayerLibraries?.current.holies?'?library='+encodeURIComponent(window.PlayerLibraries.current.holies):'' ),{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,cache:'no-store'});const v=await r.json();if(!r.ok)throw Error(v.error||'圣迹库接口失败');if(library!==currentLibrary())return v;items=v.holies;loadedLibrary=library;if(!items.some(i=>i.id===selected)){selected=items[0]?.id||'';draft=structuredClone(items[0]||blank());}for(const update of subscribers)update();return v;}
 function drawList(){if(!sidebar.children.length)sidebar.append(el('h3','选择职业'),list);list.replaceChildren();for(const item of items){const b=el('button',item.kind);b.type='button';b.className=item.id===selected?'selected':'';b.setAttribute('aria-pressed',String(item.id===selected));b.onclick=()=>{selected=item.id;draft=structuredClone(item);drawList();drawForm();};list.append(b);}if(!items.length)list.append(el('p','暂无圣迹'));}
 function table(headers,rows){const wrap=el('div');wrap.style.overflowX='auto';const t=el('table');t.className='holy-attributes';const head=el('tr');for(const title of headers)head.append(el('th',title));t.append(head);for(const values of rows){const tr=el('tr');for(const value of values)tr.append(el('td',String(value)));t.append(tr);}wrap.append(t);return wrap;}
 function drawOverview(result){overview.replaceChildren(el('h3','各职业属性总览'),table(['职业',...attrs.map(([,label])=>label)],items.map(item=>{const values=item.id===selected&&result?result.total:item.attributes;return [item.kind,...attrs.map(([k])=>values[k]??0)];})));}
 function drawForm(){
  form.replaceChildren();form.append(el('h3',draft.kind+' · 圣迹与日冕尖碑'));
  const legacy=draft.holyLevel===undefined;
  if(legacy)form.append(el('p','此条目保留旧版手填属性。请选择等级并保存，以切换为按等级计算；保存前角色面板仍使用原属性。'));
  draft.holyLevel??=100;draft.obeliskLevel??=600;
  const controls=el('div');controls.className='special-source-grid';form.append(controls);
  const holy=el('select');holy.setAttribute('aria-label','圣迹等级');for(const level of Object.keys(holyLevels)){const o=el('option',level+'级');o.value=level;holy.append(o);}holy.value=draft.holyLevel;
  const obelisk=el('input');obelisk.type='number';obelisk.min=0;obelisk.step=1;obelisk.required=true;obelisk.value=draft.obeliskLevel;obelisk.setAttribute('aria-label','日冕尖碑等级');
  for(const [label,input] of [['圣迹等级',holy],['日冕尖碑等级',obelisk]]){const row=el('label');row.className='field';row.append(el('span',label),input);controls.append(row);}
  form.append(el('p','圣迹按所提供的等级表计算；日冕尖碑每30级循环一次，各职业仅累加对应等级的属性。'));
  const preview=el('div');form.append(preview);
  function refresh(){
   draft.holyLevel=Number(holy.value);draft.obeliskLevel=obelisk.value===''?null:Number(obelisk.value);
   const result=levelAttributes(draft.kind,draft.holyLevel,draft.obeliskLevel);preview.replaceChildren();
   obelisk.setCustomValidity(result?'':'请填写非负整数等级');drawOverview(result);if(!result)return;
   draft.attributes=result.total;
   preview.append(el('h4','当前职业属性'),table(['属性','圣迹','日冕尖碑','合计'],attrs.map(([k,label])=>[label,result.holy[k],result.obelisk[k],result.total[k]])));
  }
  holy.onchange=refresh;obelisk.oninput=refresh;refresh();
  const actions=el('div');actions.className='configuration-actions';const save=el('button','保存圣迹');save.type='submit';save.className='primary';actions.append(save);form.append(actions);
  form.onsubmit=async e=>{e.preventDefault();if(!form.reportValidity())return;save.disabled=true;try{const result=await request('/'+encodeURIComponent(selected),'PUT',draft);selected=result.item.id;draft=structuredClone(result.item);drawList();drawForm();window.showToast('圣迹等级已保存，角色面板已更新');}catch(e){window.showToast(e.message);save.disabled=false;}};
 }
 window.HolyLibrary={levelAttributes,isReady:()=>loadedLibrary===currentLibrary(),resolve(s,profession){
  if(loadedLibrary!==currentLibrary())return false;
  const item=items.find(i=>i.kind===profession);
  s.selectedHoly=item?structuredClone(item):null;
  s.holy=Object.fromEntries(attrs.map(([k])=>[k,item?.attributes[k]??0]));
  s.holyCustom=true;s.holyProfession=profession;return true;
 },attach(host,s,onChange){const picker=el('select');picker.setAttribute('aria-label','从圣迹库选择');host.append(picker);function render(){picker.replaceChildren();const empty=el('option','自动按职业设置');empty.value='';picker.append(empty);for(const item of items){const o=el('option',item.name+' · '+item.kind);o.value=item.id;picker.append(o);}if(s.selectedHoly&&!items.some(i=>i.id===s.selectedHoly.id)){const o=el('option',s.selectedHoly.name+'（已保存属性）');o.value=s.selectedHoly.id;picker.append(o);}picker.value=s.selectedHoly?.id||'';}picker.onchange=()=>{const item=items.find(i=>i.id===picker.value);s.selectedHoly=item?structuredClone(item):null;s.holy=item?structuredClone(item.attributes):{};s.holyCustom=!!item;onChange();};subscribers.add(()=>{onChange();render();});render();if(loadedLibrary!==currentLibrary())request().catch(e=>window.showToast(e.message));}};
 if(window.PlayerLibraries){const bar=document.createElement('div');heading.after(bar);window.PlayerLibraries.mount(bar,'holies','默认圣迹库',async()=>{await request();drawList();drawForm();});}
 document.querySelector('#open-holies-library').onclick=async()=>{try{await request();drawList();drawForm();dialog.showModal();}catch(e){window.showToast(e.message);}};
})();
