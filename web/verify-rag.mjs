import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
await mkdir('evidence',{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:false,args:['--enable-features=WebMachineLearningNeuralNetwork']});
try {
  const page=await browser.newPage({viewport:{width:1360,height:1000}});
  const health=await (await page.request.get('http://127.0.0.1:8767/api/health')).json();
  if(health.generation!=='llamacpp-local')throw new Error('Expected llama.cpp backend');
  const errors=[],external=[],generationRequests=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.context().route('**/*',route=>{
    if(new URL(route.request().url()).hostname==='127.0.0.1')return route.continue();
    external.push(route.request().url());return route.abort();
  });
  page.on('request',r=>{if(r.url().endsWith('/generate'))generationRequests.push(r.postDataJSON());});
  await page.goto('http://127.0.0.1:8767');
  await page.locator('#file').setInputFiles('test-results/rag-fiction.pdf');
  const uploadPromise=page.waitForResponse(r=>r.url().endsWith('/api/documents')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Importer le document'}).click();
  const uploaded=await (await uploadPromise).json();
  await page.waitForFunction(()=>document.querySelector('#heading').textContent==='rag-fiction.pdf');
  await page.locator('#question').fill('Quel est le budget total du projet Azur ?');
  await page.getByRole('button',{name:'Poser la question'}).click();
  console.log('Real browser retrieval and Phi-4 generation running…');
  const response=await page.waitForResponse(r=>r.url().endsWith('/generate'),{timeout:300000});
  const result=await response.json();
  if(!response.ok())throw new Error(JSON.stringify(result));
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Réponse terminée'));
  if(!/48[\s\u202f\u00a0.,]*275/.test(result.answer))throw new Error('Montant attendu absent : '+result.answer);
  if(!/\[S\d+\]/.test(result.answer))throw new Error('Citation absente : '+result.answer);
  if(!result.sources.some(s=>s.page===2 && s.text.includes('48 275')))throw new Error('Source page 2 absente.');
  if(result.warning)throw new Error(result.warning);
  const screenshot='evidence/rag-webnn-llamacpp.png';
  await page.screenshot({path:screenshot,fullPage:true});
  await page.reload();
  const documents=await (await page.request.get('http://127.0.0.1:8767/api/documents')).json();
  await page.locator('#docs .document').nth(documents.findIndex(d=>d.id===uploaded.document.id)).click();
  await page.getByRole('button',{name:'Préparer la recherche WebNN'}).click();
  await page.waitForFunction(()=>document.querySelector('#indexStatus').textContent.includes('Index local retrouvé'),null,{timeout:60000});
  const report={date:new Date().toISOString(),browser:await page.evaluate(()=>navigator.userAgent),generationBackend:health.generation,webnnEnabled:await page.evaluate(()=>!!navigator.ml),result,
    generationRequests,cacheReloadPassed:true,externalRequests:external,pageErrors:errors,screenshot};
  await writeFile('evidence/rag-webnn-llamacpp.json',JSON.stringify(report,null,2));
  console.log(JSON.stringify(report));
  if(errors.length||external.length)throw new Error('Unexpected page error or external request.');
  await page.setViewportSize({width:390,height:844});
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw new Error('Mobile overflow');
}finally{await browser.close();}
