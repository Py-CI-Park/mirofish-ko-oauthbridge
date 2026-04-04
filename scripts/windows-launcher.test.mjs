import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const viteConfigPath = path.join(rootDir, 'frontend', 'vite.config.js');
const runBatPath = path.join(rootDir, 'run.bat');
const stopBatPath = path.join(rootDir, 'stop.bat');
const mainViewPath = path.join(rootDir, 'frontend', 'src', 'views', 'MainView.vue');
const processViewPath = path.join(rootDir, 'frontend', 'src', 'views', 'Process.vue');

test('frontend vite config honors FRONTEND_PORT', async () => {
  process.env.FRONTEND_PORT = '3100';
  process.env.BACKEND_PORT = '5100';
  const moduleUrl = `${pathToFileURL(viteConfigPath).href}?t=${Date.now()}`;
  const { default: config } = await import(moduleUrl);

  assert.equal(config.server.port, 3100);
  assert.equal(config.server.proxy['/api'].target, 'http://localhost:5100');
});

test('run.bat exposes frontend port configuration', async () => {
  const content = await readFile(runBatPath, 'utf8');

  assert.match(content, /FRONTEND_PORT/i);
  assert.match(content, /FRONTEND_URL/i);
  assert.match(content, /BACKEND_PORT/i);
  assert.match(content, /BRIDGE_PORT|PORT=%BRIDGE_PORT%/i);
  assert.match(content, /LLM_BASE_URL/i);
  assert.match(content, /VITE_API_BASE_URL/i);
});

test('stop.bat exists for Windows shutdown flow', async () => {
  const content = await readFile(stopBatPath, 'utf8');

  assert.match(content, /taskkill|Stop-Process/i);
});

test('bridge error UI does not hardcode a single bridge port', async () => {
  const [mainView, processView] = await Promise.all([
    readFile(mainViewPath, 'utf8'),
    readFile(processViewPath, 'utf8'),
  ]);

  assert.doesNotMatch(mainView, /127\.0\.0\.1:8787\/health/);
  assert.doesNotMatch(processView, /127\.0\.0\.1:8787\/health/);
});
