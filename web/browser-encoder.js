import * as ort from 'onnxruntime-web/all';
import { Tokenizer } from '@huggingface/tokenizers';
ort.env.wasm.numThreads=1;
ort.env.wasm.proxy=false;
ort.env.wasm.wasmPaths=new URL('/runtime/',self.location.href).href;
export const MODEL_KEY='minilm-aff7a1dc4e8a1ea593e6ea21e95c22ef0a25966f-fp32-window128-stride96-v1';
export async function createEncoder(provider) {
  if(provider!=='wasm' && !navigator.ml) throw new Error('WebNN n’est pas activé dans ce navigateur. Ouvrez cette version avec demarrer-webnn.bat.');
  const configs=await Promise.all(['tokenizer.json','tokenizer_config.json'].map(async file=>{
    const response=await fetch('/model/'+file);
    if(!response.ok) throw new Error('Modèle local absent. Lancez installer-webnn.bat.');
    return response.json();
  }));
  const tokenizer=new Tokenizer(...configs);
  const session=await ort.InferenceSession.create('/model/model.onnx',{
    executionProviders:provider==='wasm'?['wasm']:[{name:'webnn',deviceType:provider}],
    freeDimensionOverrides:{batch_size:1,sequence_length:128},
    externalData:[{path:'model.onnx_data',data:'/model/model.onnx_data'}],graphOptimizationLevel:'all',
  });
  async function encodeWindow(tokens) {
    const arrays={input_ids:new BigInt64Array(128),attention_mask:new BigInt64Array(128),token_type_ids:new BigInt64Array(128)};
    tokens.forEach((id,i)=>{arrays.input_ids[i]=BigInt(id);arrays.attention_mask[i]=1n;});
    const feeds=Object.fromEntries(session.inputNames.map(name=>[name,new ort.Tensor('int64',arrays[name],[1,128])]));
    let outputs;
    try {
      outputs=await session.run(feeds);
      const result=outputs.last_hidden_state??Object.values(outputs)[0];
      if(result.dims.join(',')!=='1,128,384') throw new Error('Dimensions du modèle inattendues.');
      const vector=new Float32Array(384);
      for(let t=0;t<tokens.length;t++)for(let d=0;d<384;d++)vector[d]+=result.data[t*384+d]/tokens.length;
      const norm=Math.sqrt(vector.reduce((sum,v)=>sum+v*v,0));
      if(!norm || !Number.isFinite(norm)) throw new Error('Vecteur sémantique invalide.');
      return Array.from(vector,v=>v/norm);
    } finally {
      Object.values(feeds).forEach(t=>t.dispose());
      if(outputs)Object.values(outputs).forEach(t=>t.dispose());
    }
  }
  async function encode(text) {
    const ids=tokenizer.encode(text).ids;
    const content=ids.slice(1,-1),vectors=[];
    // Toutes les fenêtres du passage sont couvertes, y compris sa fin.
    for(let start=0;start<Math.max(1,content.length);start+=96) {
      vectors.push(await encodeWindow([ids[0],...content.slice(start,start+126),ids.at(-1)]));
      if(start+126>=content.length)break;
    }
    return vectors;
  }
  return {encode,release:()=>session.release()};
}
