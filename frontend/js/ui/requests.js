"use strict";
(()=>{
 if(!['http:','https:'].includes(location.protocol))return;
 const nativeFetch=fetch,cache=new Map(),inflight=new Map();let startup=true,generation=0;
 const api=window.AppRequests={selections:{},finish(){startup=false;cache.clear();},ready:null};
 function keyFor(input){const url=new URL(String(input),location.href);if(url.origin!==location.origin||!url.pathname.startsWith('/api/'))return null;if(url.searchParams.get('library')==='')url.searchParams.delete('library');url.searchParams.sort();return url.pathname+url.search;}
 function read(input,options={}){
  const key=keyFor(input),method=(options.method||'GET').toUpperCase();
  if(!key)return nativeFetch(input,options);
  if(method!=='GET'){generation++;cache.clear();inflight.clear();return nativeFetch(input,options);}
  let pending=(startup&&cache.get(key))||inflight.get(key);
  if(!pending){const version=generation;pending=nativeFetch(input,options).then(response=>{if(!response.ok&&cache.get(key)===pending)cache.delete(key);return response;});inflight.set(key,pending);if(startup)cache.set(key,pending);pending.then(()=>{if(inflight.get(key)===pending)inflight.delete(key);if(version!==generation&&cache.get(key)===pending)cache.delete(key);},()=>{if(inflight.get(key)===pending)inflight.delete(key);if(cache.get(key)===pending)cache.delete(key);});}
  return pending.then(response=>response.clone());
 }
 api.ready=read('/api/configurations',{cache:'no-store'}).then(async response=>{if(!response.ok)return;const data=await response.json(),active=(data.configurations||[]).find(item=>item.id===data.activeId);api.selections={...(active?.configuration.librarySelections||{})};if(window.PlayerLibraries)Object.assign(window.PlayerLibraries.current,api.selections);}).catch(()=>{});
 api.fetch=async(input,options)=>{await api.ready;return read(input,options);};
})();
