import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';
import {JOINTS,DEFAULT_POSE,posterSVG} from './biped-scene.mjs';
const here=dirname(fileURLToPath(import.meta.url)),root=resolve(here,'../..');
const [scene,viewer,template]=await Promise.all(['biped-scene.mjs','biped-viewer.mjs','joint-viewer.template.html'].map(p=>readFile(resolve(here,p),'utf8')));
const poster=posterSVG();
let jointHTML='';
for(const [i,[id,label,min,max]] of JOINTS.entries()){
  if(i===0||i===3)jointHTML+=`<p class="side-heading">${i===0?'LEFT / 왼쪽':'RIGHT / 오른쪽'}</p>`;
  jointHTML+=`<div class="joint"><div class="joint-line"><label for="${id}">${label}</label><output id="${id}-value" for="${id}" aria-live="off">${DEFAULT_POSE[id]}°</output></div><input id="${id}" type="range" min="${min}" max="${max}" step="1" value="${DEFAULT_POSE[id]}" aria-describedby="model-limit"></div>`;
}
const script=scene.replace(/^export /gm,'')+'\n'+viewer;
if(script.includes('</script'))throw new Error('Unexpected script closing tag');
const html=template.replace('%%POSTER%%',poster).replace('%%JOINTS%%',jointHTML).replace('%%SCRIPT%%',script);
if(/%%[A-Z]+%%/.test(html))throw new Error('Unreplaced template token');
await writeFile(resolve(root,'static/visuals/joint-concepts-3d.html'),html);
console.log('Wrote offline joint concepts viewer (official simulator launcher preserved)');
