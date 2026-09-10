const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/chatboard/web_static/assets/app.js', 'utf8');
const start = source.indexOf('async function frontendFetch(');
const end = source.indexOf('\nasync function api(', start);
assert(start >= 0 && end > start);
const calls = [];
let session = { csrf_token: 'synthetic-csrf' };
let sessionOK = true;
const sandbox = {
  URL, Headers, window: { location: { origin: 'https://board.example' } },
  fetch: async (target, options) => {
    calls.push({ target, options });
    return target === '/api/session'
      ? { ok: sessionOK, status: 503, json: async () => session }
      : { ok: true, status: 200 };
  },
};
vm.createContext(sandbox);
vm.runInContext(source.slice(start, end), sandbox);
(async () => {
  for (const method of ['POST', 'PATCH', 'DELETE']) {
    calls.length = 0;
    await sandbox.frontendFetch('/api/backend-profiles/test', {
      method, body: '{}', credentials: 'include', headers: { 'Content-Type': 'application/json', 'X-Custom': 'kept' },
    });
    assert.equal(calls.length, 2);
    assert.equal(calls[0].target, '/api/session');
    assert.equal(calls[0].options.cache, 'no-store');
    const request = calls[1];
    assert.equal(request.options.headers.get('X-CSRF-Token'), 'synthetic-csrf');
    assert.equal(request.options.headers.get('X-Custom'), 'kept');
    assert.equal(request.options.credentials, 'same-origin');
    assert.equal(request.options.body, '{}');
  }
  for (const method of ['GET', 'HEAD', 'OPTIONS']) {
    calls.length = 0;
    await sandbox.frontendFetch('/api/pages', { method });
    assert.equal(calls.length, 1);
    assert.equal(calls[0].options.headers.get('X-CSRF-Token'), null);
  }
  for (const target of ['https://remote.example/api/pages', '//remote.example/api/pages']) {
    calls.length = 0;
    await assert.rejects(sandbox.frontendFetch(target, { method: 'POST' }), /same-origin/);
    assert.equal(calls.length, 0, 'reject remote target before fetching CSRF');
  }
  calls.length = 0;
  sessionOK = false;
  await assert.rejects(sandbox.frontendFetch('/api/logout', { method: 'POST' }), /session unavailable/);
  assert.equal(calls.length, 1);
  sessionOK = true;
  session = { csrf_token: null };
  calls.length = 0;
  await sandbox.frontendFetch('/api/backends/remote/api/cards', { method: 'PATCH', body: '{}' });
  assert.equal(calls.length, 2);
  assert.equal(calls[1].target, '/api/backends/remote/api/cards');
  assert.equal(calls[1].options.headers.get('X-CSRF-Token'), null);
  console.log('frontendFetch runtime: writes, reads, origin, session failure, proxy and disabled auth PASS');
})().catch(error => { console.error(error); process.exitCode = 1; });
