import {createEncoder, MODEL_KEY} from './browser-encoder.js';
let encoder, provider, indexed=[], key=null;
const dot=(a,b)=>a.reduce((sum,v,i)=>sum+v*b[i],0);
async function cache(action,key,value) {
  const db=await new Promise((resolve,reject)=>{
    const request=indexedDB.open('localdoc-webnn-vectors',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('indexes');
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
  });
  try{return await new Promise((resolve,reject)=>{
    const tx=db.transaction('indexes',action==='get'?'readonly':'readwrite');
    const store=tx.objectStore('indexes');
    const request=action==='get'?store.get(key):store.put(value,key);
    tx.oncomplete=()=>resolve(request.result);tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);
  });}finally{db.close();}
}
self.onmessage=async({data})=>{
  const {requestId,type}=data;
  const progress=message=>self.postMessage({requestId,type:'progress',message});
  try {
    if(!encoder||provider!==data.provider) {
      progress('Préparation du moteur de recherche local…');
      await encoder?.release();encoder=null;key=null;indexed=[];
      encoder=await createEncoder(data.provider);provider=data.provider;
    }
    if(type==='index') {
      key=null;indexed=[];
      const nextKey=`${MODEL_KEY}:${data.sha256}`;
      let saved;
      try{saved=await cache('get',nextKey);}catch{}
      if(saved?.length===data.chunks.length && saved.every((r,i)=>r.id===data.chunks[i].id && r.vectors?.length && r.vectors.every(v=>v.length===384 && v.every(Number.isFinite)))) {
        indexed=saved;key=nextKey;
        self.postMessage({requestId,type:'result',result:{cached:true,count:indexed.length,key,provider}});return;
      }
      const start=performance.now();
      for(let i=0;i<data.chunks.length;i++) {
        progress(`Préparation du document : ${i+1}/${data.chunks.length} passages…`);
        const chunk=data.chunks[i];
        indexed.push({id:chunk.id,vectors:await encoder.encode(chunk.content)});
      }
      key=nextKey;
      let cacheWarning=null;
      try{await cache('put',key,indexed);}catch{cacheWarning='Le navigateur n’a pas pu conserver l’index. Il reste utilisable dans cette fenêtre.';}
      self.postMessage({requestId,type:'result',result:{cached:false,count:indexed.length,key,provider,elapsedMs:performance.now()-start,cacheWarning}});
    } else if(type==='search') {
      if(!key||key!==data.key)throw new Error('Préparez à nouveau le document sélectionné.');
      const queries=await encoder.encode(data.question);
      const semantic=indexed.map(chunk=>({id:chunk.id,score:Math.max(...queries.flatMap(q=>chunk.vectors.map(v=>dot(q,v))))})).sort((a,b)=>b.score-a.score);
      const fused=new Map();
      for(const [rank,row]of semantic.slice(0,35).entries())fused.set(row.id,{id:row.id,semanticScore:row.score,score:1/(61+rank)});
      for(const [rank,row]of data.lexical.entries()) {
        const hit=fused.get(row.id)??{id:row.id,semanticScore:null,score:0};hit.score+=1/(61+rank);fused.set(row.id,hit);
      }
      self.postMessage({requestId,type:'result',result:{hits:[...fused.values()].sort((a,b)=>b.score-a.score).slice(0,6),provider}});
    } else throw new Error('Opération inconnue.');
  }catch(error){key=null;self.postMessage({requestId,type:'error',error:`${error.message??error}`});}
};
