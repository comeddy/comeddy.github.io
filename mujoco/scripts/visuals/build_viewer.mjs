import {readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {dirname, resolve} from 'node:path';
const here = dirname(fileURLToPath(import.meta.url));
const [source, style, template] = await Promise.all(
  ['microduck-embed.mjs', 'microduck-embed.css', 'biped-viewer.template.html'].map(p => readFile(resolve(here, p), 'utf8'))
);
const script = source.replace(/^export /gm, '');
if (script.includes('</script')) throw new Error('Unexpected script terminator');
const html = template.replace('%%STYLE%%', style).replace('%%SCRIPT%%', script);
if (/%%[A-Z]+%%/.test(html)) throw new Error('Unresolved template token');
await writeFile(resolve(here, '../../static/visuals/biped-3d.html'), html);
console.log('Wrote official Microduck simulator launcher (external app, no bundled robot assets)');
