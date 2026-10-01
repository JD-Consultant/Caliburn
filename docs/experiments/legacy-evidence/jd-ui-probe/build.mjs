import { build } from 'esbuild';
await build({ entryPoints: ['app.jsx'], bundle: true, outfile: 'public/app.js', format: 'esm', platform: 'browser', jsx: 'automatic', sourcemap: true, define: { 'process.env.NODE_ENV': '"development"' } });
await build({ entryPoints: ['render.jsx'], bundle: true, outfile: 'results/render-server.mjs', format: 'esm', platform: 'node', packages: 'external', jsx: 'automatic' });
console.log('Built real React Plate client and shared SSR renderer.');
