'use strict';
(() => {
 const model=window.SkillModel, key='dungeon2-skill-library-v1';
 const $=s=>document.querySelector(s), form=$('#skill-form'), dialog=$('#skill-editor-dialog');
 const names={strength:'力量',magic:'魔力',technique:'技巧',speed:'速度',constitution:'体质',hitPoint:'血量',weaponPower:'武威'};
 let library=[],editingId='',draftDirty=false,noticeTimer;
 const element=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 function message(text){$('#skill-message').textContent=text;}
 function notify(text){window.showToast(text);}
 function numeric(name,label,value=0,max){const row=element('label',undefined,'field');row.append(element('span',label));const input=element('input');input.type='number';input.name=name;input.min=0;input.step='any';input.required=true;input.defaultValue=String(value);input.value=value;if(max!==undefined)input.max=max;row.append(input);return row;}
 const input=name=>form.elements.namedItem(name);
 const value=name=>input(name).value;
 const num=name=>Number(value(name));
 const set=(name,v)=>{input(name).value=v;};
 function jobOption(value,label){const option=element('option',label);option.value=value;return option;}
 function renderJobOptions(profession,selected='',legacy=''){
  const select=input('skillJob');select.replaceChildren(jobOption('','请选择转职'));
  const found=model.professions.find(p=>p.name===profession);
  if(found)for(const job of found.jobs)select.append(jobOption(job,job));
  else if(profession==='legacy'&&legacy)select.append(jobOption(legacy,legacy+'（原配置）'));
  select.value=selected;select.disabled=!profession;
 }
 function loadJob(job){
  const primary=input('skillProfession');primary.replaceChildren(jobOption('','请选择职业'));
  model.professions.forEach(p=>primary.append(jobOption(p.name,p.name)));
  const found=model.findProfession(job);
  if(job&&!found)primary.append(jobOption('legacy','原职业（未分类）'));
  primary.value=found?found.name:job?'legacy':'';
  renderJobOptions(primary.value,job,job);
 }
 input('skillProfession').addEventListener('change',()=>renderJobOptions(value('skillProfession')));

 for(const attr of [...model.attributes,'weaponPower'])$('#skill-coefficients').append(numeric('coefficient-'+attr,names[attr]+'倍率',attr==='weaponPower'?1:0));
 for(const attr of ['strength','magic','technique','speed'])$('#debuff-coefficients').append(numeric('debuff-'+attr,names[attr]+'倍率'));
 for(const target of model.conversionTargets){const row=element('div',undefined,'conversion-row');row.dataset.conversion=target;
  const toggle=element('label',undefined,'conversion-toggle');toggle.append(element('span','转化为'+names[target]));const check=element('input');check.type='checkbox';check.className='switch';check.name='conversion-enabled-'+target;check.setAttribute('aria-label','启用转化为'+names[target]);toggle.append(check);row.append(toggle);
  const columns=element('div',undefined,'conversion-values');for(const attr of model.attributes)columns.append(numeric('conversion-'+target+'-'+attr,names[attr]));row.append(columns);$('#buff-conversions').append(row);
 }
 $('#skill-regeneration-fields').append(numeric('regenBase','基础数值'));
 for(const attr of model.attributes.slice(0,5)){const field=numeric('regen-'+attr,names[attr]+'系数');field.append(element('span','%','field-unit'));$('#skill-regeneration-fields').append(field);}
 function conversionsState(){const regen=value('buffType')==='regeneration';$('#skill-regeneration-fields').hidden=!regen;$('#buff-conversions').hidden=regen;$('#skill-conversion-heading').hidden=regen;$('#skill-buff-base-field').hidden=regen;input('buffBase').disabled=regen;input('regenBase').disabled=!regen||value('effectKind')!=='buff';$('#skill-buff-help').textContent=regen?'每秒回复＝（基础数值＋五维属性×对应系数之和）×（1＋回复效果%）×（1＋辉印回复%）。系数填写百分比，施加1秒后首次回复，受敌方回春降低影响。':'每行填写属性转化系数。';for(const attr of model.attributes.slice(0,5))input('regen-'+attr).disabled=!regen||value('effectKind')!=='buff';for(const target of model.conversionTargets){const enabled=input('conversion-enabled-'+target).checked;const row=form.querySelector('[data-conversion="'+target+'"]');row.classList.toggle('inactive',!enabled);for(const attr of model.attributes)input('conversion-'+target+'-'+attr).disabled=regen||!enabled||value('effectKind')!=='buff';}}
 function effectState(){const healing=value('damageType')==='none';$('#skill-targeting-field').hidden=healing;input('targeting').disabled=healing;$('.skill-race-row').hidden=healing;$('#skill-healing-row').hidden=!healing;input('raceBonus').disabled=healing;input('raceMultiplier').disabled=healing;input('healingRecipient').disabled=!healing;const kind=value('effectKind');for(const type of ['debuff','buff']){const section=$('#'+type+'-section');section.hidden=kind!==type;section.disabled=kind!==type;}conversionsState();}
 function collect(){const base=model.blank();return {...base,id:editingId,name:value('skillName'),job:value('skillJob'),damageType:value('damageType'),healingRecipient:value('healingRecipient'),targeting:value('targeting'),ignoreTaunt:value('ignoreTaunt')==='true',cooldown:num('cooldown'),lifesteal:num('skillLifesteal'),hitRate:num('skillHitRate'),criticalRate:num('skillCriticalRate'),coefficients:Object.fromEntries([...model.attributes,'weaponPower'].map(k=>[k,num('coefficient-'+k)])),raceBonus:{race:value('raceBonus'),multiplier:num('raceMultiplier')},effect:value('effectKind')==='none'?null:value('effectKind')==='debuff'?{kind:'debuff',type:value('debuffType'),applicationRate:num('applicationRate'),baseValue:num('debuffBase'),duration:num('debuffDuration'),coefficients:Object.fromEntries(['strength','magic','technique','speed'].map(k=>[k,num('debuff-'+k)]))}:{kind:'buff',type:value('buffType'),triggerRate:num('buffTriggerRate'),baseValue:num(value('buffType')==='regeneration'?'regenBase':'buffBase'),duration:num('buffDuration'),recipient:value('buffRecipient'),skillType:value('buffSkillType'),...(value('buffType')==='regeneration'?{coefficients:Object.fromEntries(model.attributes.slice(0,5).map(k=>[k,num('regen-'+k)/100]))}:{}),conversions:model.conversionTargets.map(target=>({target,enabled:input('conversion-enabled-'+target).checked,coefficients:input('conversion-enabled-'+target).checked?Object.fromEntries(model.attributes.map(k=>[k,num('conversion-'+target+'-'+k)])):model.zeros()}))}};}
 function load(skill){form.reset();editingId=skill.id;set('skillName',skill.name);loadJob(skill.job);set('damageType',skill.damageType);set('healingRecipient',skill.healingRecipient||'self');set('targeting',skill.targeting||'single');set('ignoreTaunt',String(skill.ignoreTaunt??false));set('cooldown',skill.cooldown);set('skillLifesteal',skill.lifesteal??0);set('skillHitRate',skill.hitRate);set('skillCriticalRate',skill.criticalRate);for(const attr of [...model.attributes,'weaponPower'])set('coefficient-'+attr,skill.coefficients[attr]);set('raceBonus',skill.raceBonus.race);set('raceMultiplier',skill.raceBonus.multiplier);set('effectKind',skill.effect?.kind||'none');
  if(skill.effect?.kind==='debuff'){const e=skill.effect;set('debuffType',e.type);set('applicationRate',e.applicationRate);set('debuffBase',e.baseValue);set('debuffDuration',e.duration);for(const attr of ['strength','magic','technique','speed'])set('debuff-'+attr,e.coefficients[attr]);}
  if(skill.effect?.kind==='buff'){const e=skill.effect;set('buffType',e.type);set('buffTriggerRate',e.triggerRate);set('buffBase',e.baseValue);set('regenBase',e.baseValue);set('buffDuration',e.duration);set('buffRecipient',e.recipient);set('buffSkillType',e.skillType);for(const attr of model.attributes.slice(0,5))set('regen-'+attr,(e.coefficients?.[attr]??0)*100);for(const row of e.conversions){input('conversion-enabled-'+row.target).checked=row.enabled;for(const attr of model.attributes)set('conversion-'+row.target+'-'+attr,row.coefficients[attr]);}}
  effectState();draftDirty=false;$('#skill-edit-title').textContent=editingId?'编辑技能':'创建技能';$('#skill-save').textContent=editingId?'保存修改':'保存到技能库';$('#skill-duplicate').disabled=!editingId;$('#skill-json').hidden=true;message('');
 }
 function discardDraft(){return !draftDirty||window.confirm('当前技能有未保存的修改，是否放弃这些修改？');}
 const professionFilter=element('select'),jobFilter=element('select');professionFilter.id='skill-profession-filter';jobFilter.id='skill-job-filter';professionFilter.setAttribute('aria-label','按职业大类筛选技能');jobFilter.setAttribute('aria-label','按细分职业筛选技能');professionFilter.append(jobOption('','全部职业'));model.professions.forEach(p=>professionFilter.append(jobOption(p.name,p.name)));professionFilter.value='';
 $('#skill-search').after(professionFilter,jobFilter);
 function updateJobFilter(){jobFilter.replaceChildren(jobOption('','全部转职'));const family=model.professions.find(p=>p.name===professionFilter.value);const jobs=family?family.jobs:model.professions.flatMap(p=>p.jobs);jobs.forEach(job=>jobFilter.append(jobOption(job,job)));jobFilter.value='';}
 updateJobFilter();professionFilter.addEventListener('change',()=>{updateJobFilter();renderList();});jobFilter.addEventListener('change',renderList);
 function renderList(){window.onSkillLibraryChange?.(library);const list=$('#created-skill-list');list.replaceChildren();const query=$('#skill-search').value.trim().toLowerCase();const items=library.filter(s=>(!professionFilter.value||model.findProfession(s.job)?.name===professionFilter.value)&&(!jobFilter.value||s.job===jobFilter.value)&&(s.name+' '+s.job).toLowerCase().includes(query));$('#skill-library-count').textContent=library.length+' 个技能';
  if(!items.length)list.append(element('p',library.length?'没有匹配的技能。':'还没有技能。填写右侧表单，创建第一个技能。','skill-empty'));
  for(const skill of items){const button=element('button',undefined,'created-skill-item');button.type='button';button.classList.toggle('selected',skill.id===editingId);button.append(element('strong',skill.name),element('small',skill.job+' · '+({physical:'物理',magic:'魔法',none:'回复技能'}[skill.damageType])+(skill.damageType==='none'?'':' · '+(skill.targeting==='all'?'群体技能':'单体技能'))+' · '+skill.cooldown+'秒'));
   button.addEventListener('click',()=>{if(discardDraft()){load(skill);renderList();}});list.append(button);}
 }
 const useAPI=['http:','https:'].includes(window.location.protocol);
 let saving=false;
 async function request(path,method='GET',body){if(window.AppRequests)await window.AppRequests.ready;
  const response=await (window.AppRequests?.fetch||fetch)(path,{method,headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,cache:'no-store'});
  let result;try{result=await response.json();}catch{throw new Error('接口没有返回有效数据，请运行server.py并从服务地址打开页面');}
  if(!response.ok)throw new Error(result.error||'接口请求失败');return result;
 }
 async function commit(next,skill=null,update=false){
  await ready;
  const validated=model.library({schemaVersion:1,skills:next}).skills;
  if(useAPI){const data=skill?await request(update?'/api/skills/'+encodeURIComponent(skill.id):'/api/skills',update?'PUT':'POST',skill):await request('/api/skills/import','POST',{schemaVersion:1,skills:validated});library=model.library(data).skills;}
  else{localStorage.setItem(key,JSON.stringify({schemaVersion:1,skills:validated}));library=validated;}
 }
 form.addEventListener('input',()=>{draftDirty=true;message('有未保存的修改');$('#skill-json').hidden=true;});
 form.addEventListener('change',()=>{effectState();draftDirty=true;message('有未保存的修改');});
 form.addEventListener('submit',async event=>{event.preventDefault();if(saving||!form.reportValidity())return;saving=true;$('#skill-save').disabled=true;try{await ready;const draft=collect();draft.id=editingId||('skill_'+crypto.randomUUID());const skill=model.validate(draft);const next=library.filter(s=>s.id!==skill.id);next.push(skill);await commit(next,skill,Boolean(editingId));load(skill);renderList();message(useAPI?'已保存到项目文件 data/skills.json':'已保存到当前浏览器的技能库');notify('技能已保存');}catch(err){message('保存失败：'+err.message);notify('保存失败：'+err.message);}finally{saving=false;$('#skill-save').disabled=false;}});
 $('#new-skill').addEventListener('click',()=>{if(discardDraft()){load(model.blank());renderList();}});
 $('#skill-duplicate').addEventListener('click',()=>{if(!form.reportValidity())return;try{const copy=model.validate(collect());copy.id='';copy.name=(copy.name+'（副本）').slice(0,120);load(copy);draftDirty=true;renderList();message('正在创建副本，点击保存后生成独立技能');}catch(err){message(err.message);}});
 $('#skill-preview').addEventListener('click',()=>{if(!form.reportValidity())return;try{$('#skill-json').textContent=JSON.stringify(model.validate(collect(),false),null,2);$('#skill-json').hidden=false;}catch(err){message(err.message);}});
 $('#skill-search').addEventListener('input',renderList);
 $('#open-skill-editor').addEventListener('click',()=>{renderList();dialog.showModal();});
 $('#close-skill-editor').addEventListener('click',()=>{dialog.close();});
 $('#export-skill-library').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({schemaVersion:1,skills:library},null,2)],{type:'application/json'}));const a=element('a');a.href=url;a.download='地下城堡2-技能库.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);notify('已导出保存的技能；未保存的草稿不包含在内');});
 $('#import-skill-library').addEventListener('click',()=>$('#skill-library-file').click());
 $('#skill-library-file').addEventListener('change',async event=>{const file=event.target.files[0];if(!file)return;try{if(file.size>5*1024*1024)throw new Error('文件不能超过5MB');const incoming=model.library(JSON.parse(await file.text())).skills;await ready;const next=model.merge(library,incoming);await commit(next);renderList();notify('技能库导入完成（已合并，保留原技能）');}catch(err){notify('导入失败：'+err.message);}finally{event.target.value='';}});
 let restoreError='';try{const saved=useAPI?null:localStorage.getItem(key);if(saved)library=model.library(JSON.parse(saved)).skills;}catch{restoreError='原技能库无法读取，请从备份导入恢复。';}
 load(model.blank());renderList();if(restoreError)notify(restoreError);
 const ready=useAPI?request('/api/skills').then(data=>{library=model.library(data).skills;renderList();if(!draftDirty)message('已连接项目技能文件');}):Promise.resolve();
 ready.catch(error=>notify('技能接口连接失败：'+error.message));
})();
