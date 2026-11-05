const $=id=>document.getElementById(id);
let docs=[],selected=null,chunks=[],indexKey=null,worker=null,requestId=0,busy=false;
const pending=new Map();
async function api(url,options={}) {
  const response=await fetch(url,options),data=await response.json();
  if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail??data));
  return data;
}
const post=(url,body)=>api(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
const node=(tag,value,cls)=>{const n=document.createElement(tag);n.textContent=value;if(cls)n.className=cls;return n;};
function lock(value) {
  busy=value;
  for(const id of ['uploadBtn','file','prepare','open','delete','askBtn','provider'])$(id).disabled=value;
  document.querySelectorAll('.document').forEach(n=>n.disabled=value);
}
function resetWorker(error) {
  worker?.terminate();worker=null;indexKey=null;
  for(const task of pending.values()){clearTimeout(task.timer);task.reject(new Error(error));}pending.clear();
}
function run(type,data) {
  if(!worker) {
    worker=new Worker(new URL('./rag-worker.js',import.meta.url),{type:'module'});
    worker.onmessage=({data})=>{
      const task=pending.get(data.requestId);if(!task)return;
      if(data.type==='progress'){$('indexStatus').textContent=data.message;return;}
      clearTimeout(task.timer);pending.delete(data.requestId);
      if(data.type==='error'){indexKey=null;task.reject(new Error(data.error));}else task.resolve(data.result);
    };
    worker.onerror=e=>resetWorker(e.message||'Le moteur du navigateur a rencontré une erreur.');
  }
  return new Promise((resolve,reject)=>{
    const id=++requestId;
    const timer=setTimeout(()=>resetWorker('Préparation trop longue. Réessayez ou sélectionnez explicitement WASM dans les options.'),600000);
    pending.set(id,{resolve,reject,timer});worker.postMessage({requestId:id,type,provider:$('provider').value,...data});
  });
}
async function refresh() {
  docs=await api('/api/documents');$('docs').replaceChildren();
  for(const d of docs){const button=node('button',d.name,'document'+(d.id===selected?' active':''));button.type='button';button.disabled=busy;button.append(node('small',`${d.num_pages} page(s) · ${d.chunks_count} passages`));button.onclick=()=>choose(d.id);$('docs').append(button);}
  if(!docs.length)$('docs').append(node('p','Aucun document importé.','note'));
}
async function choose(id) {
  if(busy)return;
  lock(true);indexKey=null;selected=id;chunks=[];
  $('workspace').hidden=false;$('intro').hidden=true;$('warning').textContent='';$('sources').replaceChildren();$('reply').textContent='Posez une question sur ce document.';$('timing').textContent='';$('status').textContent='';
  try {
    const result=await api(`/api/webnn/documents/${id}/chunks`);chunks=result.chunks;
    $('heading').textContent=result.document.name;
    $('meta').textContent=`${result.document.num_pages} page(s) · ${chunks.length} passages`+(result.document.ocr_needed?` · ${result.document.ocr_needed} page(s) sans texte, OCR nécessaire`:'');
    $('indexStatus').textContent='Le document sera préparé automatiquement à la première question.';
    await refresh();
  }catch(e){$('warning').textContent=e.message;$('workspace').hidden=true;$('intro').hidden=false;selected=null;}
  finally{lock(false);}
}
async function prepare() {
  if(indexKey)return;
  const doc=docs.find(d=>d.id===selected);if(!doc)throw new Error('Sélectionnez un document.');
  const result=await run('index',{sha256:doc.sha256,chunks});indexKey=result.key;
  $('indexStatus').textContent=(result.cached?'Index local retrouvé.':`${result.count} passages préparés.`)+(result.cacheWarning?' '+result.cacheWarning:' Recherche prête.');
}
function showSources(sources) {
  $('sources').replaceChildren();
  for(const source of sources){const box=node('div','','source');const link=node('a',`[${source.source_id}] · Page ${source.page}`);link.href=`/api/documents/${encodeURIComponent(selected)}/original#page=${source.page}`;link.target='_blank';link.rel='noopener';box.append(link,node('p',source.text));$('sources').append(box);}
}
$('upload').onsubmit=async e=>{
  e.preventDefault();if(busy)return;const file=$('file').files[0];if(!file)return;
  if(file.size>25*1024*1024){$('uploadStatus').textContent='Le fichier dépasse 25 Mo.';return;}
  lock(true);$('uploadStatus').textContent='Extraction du document en cours…';let id;
  try {const body=new FormData();body.append('file',file);const r=await api('/api/documents',{method:'POST',body});id=r.document.id;await refresh();$('uploadStatus').textContent=r.duplicate?'Document déjà présent.':'Document importé. Vous pouvez poser une question.';}
  catch(error){$('uploadStatus').textContent='Erreur : '+error.message;}
  finally{lock(false);}
  if(id)await choose(id);
};
$('prepare').onclick=async()=>{if(busy||!selected)return;lock(true);$('warning').textContent='';try{await prepare();}catch(e){$('warning').textContent=e.message;}finally{lock(false);}};
$('askForm').onsubmit=async e=>{
  e.preventDefault();if(busy||!selected)return;
  const question=$('question').value.trim();if(question.length<3)return;
  lock(true);const start=performance.now();$('warning').textContent='';$('reply').textContent='';$('sources').replaceChildren();$('timing').textContent='';
  try {
    $('status').textContent='Recherche des passages du document…';await prepare();
    const lexical=await post(`/api/webnn/documents/${selected}/lexical`,{question});
    const result=await run('search',{key:indexKey,question,lexical});
    const sources=result.hits.map((hit,i)=>{const c=chunks.find(c=>c.id===hit.id);return {source_id:`S${i+1}`,page:c.page,text:c.content};});
    if(!sources.length){$('reply').textContent='Aucun passage lisible trouvé dans le document.';$('status').textContent='';return;}
    showSources(sources);const retrievalMs=performance.now()-start;
    $('status').textContent='Passages retrouvés. Phi‑4 rédige la réponse en local…';
    const answer=await post(`/api/webnn/documents/${selected}/generate`,{question,chunk_ids:result.hits.map(h=>h.id)});
    $('reply').textContent=answer.answer;showSources(answer.sources);$('warning').textContent=answer.warning??'';
    $('timing').textContent=`Recherche ${(retrievalMs/1000).toFixed(1)} s · réponse ${answer.elapsed_seconds} s`;
    $('status').textContent='Réponse terminée · '+($('provider').value==='wasm'?'recherche WASM':'recherche WebNN')+' + Phi‑4 local';
  }catch(error){$('warning').textContent='Erreur : '+error.message;$('status').textContent='';if(!$('reply').textContent)$('reply').textContent='La réponse n’a pas pu être générée. Les passages déjà retrouvés restent consultables.';}
  finally{lock(false);}
};
$('provider').onchange=()=>{indexKey=null;$('indexStatus').textContent='Moteur changé. Le document sera préparé à la prochaine question.';};
$('open').onclick=()=>{if(selected)window.open(`/api/documents/${selected}/original`,'_blank','noopener');};
$('delete').onclick=async()=>{
  if(busy||!selected||!confirm('Supprimer ce document et ses données indexées ?'))return;
  lock(true);
  try{await api(`/api/documents/${selected}`,{method:'DELETE'});selected=null;chunks=[];indexKey=null;$('workspace').hidden=true;$('intro').hidden=false;$('heading').textContent='Interroger un document';await refresh();}
  catch(error){$('warning').textContent=error.message;}finally{lock(false);}
};
Promise.all([refresh(),api('/api/health')]).then(([,health])=>{$('health').textContent=`Local · recherche navigateur · réponses ${health.chat_model}`;}).catch(error=>{$('health').textContent='Service RAG indisponible';$('uploadStatus').textContent='Erreur : '+error.message;});
