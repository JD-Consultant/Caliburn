import http from 'node:http';
import fs from 'node:fs/promises';
const port = Number(process.env.JD_UI_PROBE_PORT || 4391);
const routes = { '/': ['index.html', 'text/html; charset=utf-8'], '/app.js': ['app.js', 'text/javascript; charset=utf-8'], '/app.js.map': ['app.js.map', 'application/json'], '/style.css': ['style.css', 'text/css; charset=utf-8'], '/materials.json': ['materials.json', 'application/json; charset=utf-8'] };
http.createServer(async (req, res) => {
  const route = routes[new URL(req.url, `http://127.0.0.1:${port}`).pathname];
  if (!route) { res.writeHead(404); return res.end('Not found'); }
  try { const body = await fs.readFile(new URL(`public/${route[0]}`, import.meta.url)); res.writeHead(200, { 'Content-Type': route[1], 'Cache-Control': 'no-store' }); res.end(body); }
  catch (error) { res.writeHead(500); res.end(error.message); }
}).listen(port, '127.0.0.1', () => console.log(`JD UI probe http://127.0.0.1:${port}/`));
