import { mkdir, copyFile, writeFile, rename, access } from 'node:fs/promises';
import { createWriteStream } from 'node:fs';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { fileURLToPath } from 'node:url';

process.chdir(fileURLToPath(new URL('.', import.meta.url)));
const revision = 'aff7a1dc4e8a1ea593e6ea21e95c22ef0a25966f';
await mkdir('public/model', { recursive: true });
await mkdir('public/runtime', { recursive: true });
for (const file of ['model.onnx', 'model.onnx_data', 'tokenizer.json', 'tokenizer_config.json']) {
  const target = `public/model/${file}`;
  try { await access(target); continue; } catch {}
  const source = file.startsWith('model.') ? `onnx/${file}` : file;
  console.log(`Téléchargement : ${source}`);
  const response = await fetch(`https://huggingface.co/onnx-community/all-MiniLM-L6-v2-ONNX/resolve/${revision}/${source}`);
  if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
  await pipeline(Readable.fromWeb(response.body), createWriteStream(`${target}.part`));
  await rename(`${target}.part`, target);
}
for (const file of ['ort-wasm-simd-threaded.jsep.mjs', 'ort-wasm-simd-threaded.jsep.wasm']) {
  await copyFile(`node_modules/onnxruntime-web/dist/${file}`, `public/runtime/${file}`);
}
await writeFile('public/model/provenance.json', JSON.stringify({
  model: 'onnx-community/all-MiniLM-L6-v2-ONNX', revision,
  license: 'Apache-2.0', source: `https://huggingface.co/onnx-community/all-MiniLM-L6-v2-ONNX/tree/${revision}`,
}, null, 2));
console.log('Modèle et moteur prêts : tous les fichiers seront servis localement.');
