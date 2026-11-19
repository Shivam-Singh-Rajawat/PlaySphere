// PlaySphere uses server-rendered static assets + FastAPI, not a JS bundler.
// This validates deploy inputs and both runtimes before Vercel discovers app.py.
import { readFileSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

function need(path) {
  if (!existsSync(path)) throw new Error(`Required deployment file missing: ${path}`);
}
['app.py', 'neon.ts', 'vercel.json', 'web/index.html', 'web/style.css', 'web/app.js', 'requirements.txt'].forEach(need);
const html = readFileSync('web/index.html', 'utf8');
if (!html.includes('/assets/style.css') || !html.includes('/assets/app.js')) {
  throw new Error('HTML is missing expected CSS or JavaScript asset references');
}
JSON.parse(readFileSync('vercel.json', 'utf8'));
execFileSync(process.execPath, ['--check', 'web/app.js'], { stdio: 'inherit' });
const python = process.env.PYTHON || 'python';
execFileSync(python, ['-c',
  "from pathlib import Path; [compile(Path(p).read_bytes(), p, 'exec') for p in ('app.py','seed_demo.py')]; print('Python syntax: OK')"
], { stdio: 'inherit' });
console.log('PlaySphere build validation: PASS (static assets, API, Neon config and Vercel config)');
