 'use strict';
window.WikiEquipmentDetails={create({form,after,button,E,onChange,getDraft}){
 const standard={weaponPower:'武威',strength:'力量',magic:'魔力',technique:'技巧',speed:'速度',constitution:'体质',armor:'护甲',resistance:'抗性',criticalRate:'暴击率',hitRate:'命中率',dodgeRate:'闪避率',healingBonus:'回复效果',lifesteal:'吸血',ignoreArmor:'无视护甲',ignoreResistance:'无视抗性',criticalMultiplier:'暴击伤害系数',dodge:'闪避',abnormalBonus:'异常附加率',unload:'卸负',load:'负重'};
 const ranged=new Set(['weaponPower','strength','magic','technique','speed','constitution','armor','resistance']);
 const percent=new Set(['criticalRate','hitRate','dodgeRate','healingBonus','lifesteal','criticalMultiplier','abnormalBonus']);let metadata={},inputs=[];
 const panel=E('details',undefined,'wiki-base-panel'),summary=E('summary','装备基础属性');panel.append(summary);const grid=E('div',undefined,'wiki-attribute-grid');panel.append(E('p','武威、力量、魔力、技巧、速度、体质、护甲和抗性记录上下限，其余属性填写固定值。空白表示来源未提供具体数值；这些数值记录不会自动叠加到角色面板；下方的负面免疫在角色佩戴装备后生效。保存时，公共设置同步到所有库已有的同名装备；“我的数值”仅保存到当前库，其他库的个人数值保持不变。百分比为范围进度：0%对应最小值，100%对应最大值，和“我的数值”双向换算。','skill-help'),grid);after.after(panel);
 const mainAttributes={strength:'力量',magic:'魔力',technique:'技巧',speed:'速度',constitution:'体质'},mainAttribute=E('select'),mainRow=E('label',undefined,'field wiki-main-attribute');mainAttribute.setAttribute('aria-label','装备主属性');
 for(const [key,label] of [['','未标注'],...Object.entries(mainAttributes)]){const o=E('option',label);o.value=key;mainAttribute.append(o);}
 mainRow.append(E('span','主属性'),mainAttribute);summary.after(mainRow);let attributeTitles={};
 function showMainAttribute(){for(const [key,title] of Object.entries(attributeTitles)){title.replaceChildren(E('span',standard[key]));if(key===mainAttribute.value)title.append(E('span','主属性','equipment-main-attribute-badge'));}}
 mainAttribute.addEventListener('change',()=>{metadata.mainAttribute=mainAttribute.value;showMainAttribute();onChange();});
 const immunityInputs={};const immunity=E('fieldset',undefined,'equipment-immunities');immunity.append(E('legend','免疫负面'));const immunityOptions=E('div',undefined,'equipment-immunity-options');immunity.append(immunityOptions);panel.append(immunity,E('p','属性衰减免疫只对应明确标注的力量、魔力、技巧、速度、护甲或抗性衰减；虚弱和恐惧属于独立负面效果，不受力量衰减或技巧衰减免疫影响。','skill-help'));
 for(const [key,label] of Object.entries(window.EquipmentModel.immunityLabels)){const row=E('label'),input=E('input');input.type='checkbox';input.setAttribute('aria-label','装备免疫'+label);input.addEventListener('change',onChange);row.append(input,E('span',label));immunityOptions.append(row);immunityInputs[key]=input;}
 const crystalAttrs={strength:'力量',magic:'魔力',technique:'技巧',speed:'速度',constitution:'体质'},crystalInputs={};
 const crystal=E('section',undefined,'equipment-crystal'),toggleLabel=E('label',undefined,'conversion-toggle section-label'),toggle=E('input');toggle.type='checkbox';toggle.className='switch';toggle.setAttribute('aria-label','启用晶络');toggleLabel.append(E('span','晶络'),toggle);const crystalGrid=E('div',undefined,'skill-basic-grid');crystal.append(toggleLabel,crystalGrid);panel.append(crystal);
 for(const [key,label] of Object.entries(crystalAttrs)){const row=E('label',undefined,'field'),wrap=E('div',undefined,'crystal-unit-input'),input=E('input');input.type='number';input.step='any';input.setAttribute('aria-label','晶络'+label);wrap.append(input,E('span','%'));row.append(E('span',label),wrap);crystalGrid.append(row);crystalInputs[key]=input;input.addEventListener('input',onChange);}
 function crystalState(){crystalGrid.hidden=!toggle.checked;for(const input of Object.values(crystalInputs))input.disabled=!toggle.checked;}
 toggle.addEventListener('change',()=>{crystalState();onChange();});
 const source=E('pre',undefined,'wiki-source');panel.after(source);const issues=E('p',undefined,'wiki-issues');source.after(issues);
 const progress=E('dialog',undefined,'wiki-extra-dialog');progress.append(button('×',()=>progress.close()),E('h2','百科装备整理进度'));const table=E('table',undefined,'wiki-progress-table');progress.append(table);document.body.append(progress);
 function showIssues(){issues.textContent=metadata.classificationStatus==='reviewed'?'人工核对完成':(metadata.reviewIssues||[]).length?'待补充 '+metadata.reviewIssues.length+' 项：'+metadata.reviewIssues.slice(0,2).join('；'):'已完成自动转录';source.textContent=metadata.source?'来源属性：'+metadata.source.attributes+'\n来源特效：'+metadata.source.effects:'';}
 function load(value){
  metadata=value;mainAttribute.value=value.mainAttribute||'';attributeTitles={};
  for(const [key,input] of Object.entries(immunityInputs)){input.checked=metadata.negativeImmunities?.[key]??false;input.defaultChecked=input.checked;}
  toggle.checked=metadata.crystal?.enabled??false;
  for(const [key,input] of Object.entries(crystalInputs)){input.value=metadata.crystal?.attributes?.[key]??0;input.defaultValue=input.value;}
  crystalState();metadata.baseAttributes??={};inputs=[];grid.replaceChildren();
  for(const [key,label] of Object.entries(standard)){
   const stat=metadata.baseAttributes[key]||{label,min:0,max:0,value:0,unit:percent.has(key)?'%':''};metadata.baseAttributes[key]=stat;
   const row=E('div',undefined,'wiki-attribute-row'),title=E('strong',label+(stat.unit||''));row.append(title);if(ranged.has(key))attributeTitles[key]=title;const controls={};
   if(!ranged.has(key))row.classList.add('wiki-fixed-attribute');
   for(const [field,caption] of (ranged.has(key)?[['min','最小'],['max','最大'],['ownedValue','我的数值']]:[['value','固定值']])){
    const cell=E('label'),input=E('input');input.type='number';input.step='any';input.value=(field==='value'?(stat.value??(stat.min===stat.max?stat.min:null)):stat[field])??'';input.defaultValue=input.value;
    input.placeholder=field==='ownedValue'?'可选':'未提供';input.setAttribute('aria-label',label+caption);cell.append(E('span',caption),input);row.append(cell);inputs.push({key,field,input});controls[field]=input;
   }
   if(ranged.has(key)){
    const cell=E('label',undefined,'wiki-owned-percentage'),progress=E('input');progress.type='number';progress.step='any';progress.min=0;progress.max=100;progress.placeholder='可选';progress.setAttribute('aria-label',label+'百分比');progress.title='范围进度：0%＝最小值，100%＝最大值';cell.append(E('span','百分比'),progress,E('span','%'));row.append(cell);
    const read=input=>input.value===''?null:Number(input.value),rounded=value=>Number(value.toFixed(8));
    function syncProgress(){const min=read(controls.min),max=read(controls.max),owned=read(controls.ownedValue);const valid=min!==null&&max!==null&&Number.isFinite(min)&&Number.isFinite(max)&&max>min;progress.disabled=!valid;progress.placeholder=valid?'可选':min!==null&&min===max?'固定值':'范围无效';progress.value=valid&&owned!==null&&Number.isFinite(owned)?String(rounded((owned-min)/(max-min)*100)):'';}
    for(const input of Object.values(controls))input.addEventListener('input',()=>{syncProgress();onChange();});
    progress.addEventListener('input',()=>{const value=read(progress),min=read(controls.min),max=read(controls.max);controls.ownedValue.value=value===null?'':String(rounded(min+(max-min)*value/100));onChange();});
    syncProgress();progress.defaultValue=progress.value;
   }else controls.value.addEventListener('input',onChange);
   row.append(E('small',stat.source||'来源未列出，记为0'));grid.append(row);
  }
  showMainAttribute();showIssues();
 }
 function capture(value){value.mainAttribute=mainAttribute.value;value.negativeImmunities=Object.fromEntries(Object.entries(immunityInputs).map(([key,input])=>[key,input.checked]));value.crystal={enabled:toggle.checked,attributes:Object.fromEntries(Object.entries(crystalInputs).map(([key,input])=>{const n=input.value===''?0:Number(input.value);if(!Number.isFinite(n))throw Error('晶络属性数值无效');return [key,n];}))};for(const {key,field,input} of inputs){const n=input.value===''?null:Number(input.value);if(n!==null&&!Number.isFinite(n))throw Error('属性数值无效');value.baseAttributes[key][field]=n;}for(const [key,stat] of Object.entries(value.baseAttributes||{})){if(!ranged.has(key)){stat.min=stat.max=stat.value;continue;}if(stat.min!==null&&stat.max!==null&&stat.min>stat.max)throw Error(stat.label+'最小值不能超过最大值');if(stat.ownedValue!==null&&stat.ownedValue!==undefined&&inputs.some(entry=>entry.key===key&&entry.field==='ownedValue'&&entry.input.value!==entry.input.defaultValue)&&(stat.min===null||stat.max===null||stat.ownedValue<stat.min||stat.ownedValue>stat.max))throw Error(stat.label+'我的数值必须在词条上下限内');stat.value=stat.min===stat.max?stat.min:null;}}
 function showProgress(items){table.replaceChildren();const header=E('tr');for(const label of ['分类','总数','已转录','待补充','人工核对'])header.append(E('th',label));table.append(header);const classes=[['sword','剑（战士）'],['axe','斧（野蛮人）'],['dagger','匕（潜行者）'],['staff','杖（法师）'],['gun','枪（火枪手）'],['hammer','锤（圣职）'],['armor','防具'],['accessory','饰品']];for(const [key,label] of classes){const subset=items.filter(i=>i.source?.category===key),row=E('tr');for(const v of [label,subset.length,...['converted','needsReview','reviewed'].map(s=>subset.filter(i=>i.classificationStatus===s).length)])row.append(E('td',String(v)));table.append(row);}progress.showModal();}
 return {load,capture,showProgress};
}};
