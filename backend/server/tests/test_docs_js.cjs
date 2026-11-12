const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const source = readFileSync(require('node:path').join(__dirname, '../docs_assets/docs.js'), 'utf8');

function harness(session = true, fetchImpl = async () => ({ok: true, json: async () => ({csrfToken: 'fresh'})})) {
  const calls = [];
  class Element {
    constructor(tag = 'div') { this.tag = tag; this.children = []; this.events = {}; this.hidden = false; this.value = ''; }
    append(...children) { this.children.push(...children); }
    setAttribute(name, value) { this[name] = value; }
    addEventListener(name, listener) { this.events[name] = listener; }
  }
  const elements = Object.fromEntries(['docs-status','auth-help','jwt-control','jwt-token','operations','local-docs','swagger-ui'].map(id => [id,new Element()]));
  elements['swagger-ui'].hidden = true;
  const document = {
    body: {dataset: {sessionBackend: String(session), csrfUrl: '/api/auth/csrf/', schemaUrl: '/api/schema/',
      swaggerJsUrl: '/api/docs/assets/swagger-ui-bundle.js', swaggerCssUrl: '/api/docs/assets/swagger-ui.css'}},
    head: new Element('head'),
    createElement: tag => new Element(tag),
    getElementById: id => elements[id],
    addEventListener: (event, listener) => { document[event] = listener; },
  };
  const window = {location: {origin: 'http://localhost:8000'}};
  vm.runInNewContext(source, {document, window, URL, URLSearchParams, fetch: async (...args) => {
    calls.push(args);
    return fetchImpl(...args);
  }});
  return {api: window.LastLightDocs, calls, document, window, elements};
}

test('GET sends no CSRF request and keeps browser session credentials', async () => {
  const h = harness();
  await h.api.execute('/api/runs/', 'GET');
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0][1].credentials, 'same-origin');
});

test('unsafe requests fetch fresh CSRF after login rotation', async () => {
  let generation = 0;
  const h = harness(true, async url => ({ok: true, json: async () => ({csrfToken: `token-${++generation}`})}));
  await h.api.execute('/api/auth/login/', 'POST', '{"username":"owner","password":"test"}');
  await h.api.execute('/api/auth/logout/', 'POST');
  assert.equal(h.calls[1][1].headers['X-CSRFToken'], 'token-1');
  assert.equal(h.calls[3][1].headers['X-CSRFToken'], 'token-2');
  assert.equal(h.calls[1][1].headers['Content-Type'], 'application/json');
});

test('CSRF failure blocks the write', async () => {
  const h = harness(true, async () => ({ok: false, status: 403}));
  await assert.rejects(h.api.execute('/api/runs/', 'POST', '{}'), /CSRF: HTTP 403/);
  assert.equal(h.calls.length, 1);
});

test('missing CSRF token blocks the write', async () => {
  const h = harness(true, async () => ({ok: true, json: async () => ({})}));
  await assert.rejects(h.api.execute('/api/runs/', 'POST', '{}'), /CSRF token/);
  assert.equal(h.calls.length, 1);
});

test('JWT mode sends Bearer token without contacting session endpoint', async () => {
  const h = harness(false);
  await h.api.execute('/api/runs/', 'POST', '{}', 'access-token');
  assert.equal(h.calls.length, 1);
  assert.equal(h.calls[0][1].headers.Authorization, 'Bearer access-token');
});

test('invalid JSON is rejected before any network request', async () => {
  const h = harness();
  await assert.rejects(h.api.execute('/api/runs/', 'POST', '{bad'));
  assert.equal(h.calls.length, 0);
});

test('cross-origin requests cannot leak tokens or cookies', async () => {
  const h = harness(false);
  await assert.rejects(h.api.execute('https://example.com/api/runs/', 'POST', '{}', 'secret'), /Разрешены/);
  assert.equal(h.calls.length, 0);
});

const schema = {info: {description: 'Session login'}, paths: {
  '/api/runs/{id}/': {parameters: [{name: 'id', in: 'path', required: true, schema: {type: 'integer'}}],
    get: {summary: 'Read run'}},
  '/api/auth/login/': {post: {summary: 'Login', requestBody: {content: {'application/json': {schema: {
    type: 'object', properties: {username: {type: 'string'}, password: {type: 'string'}}
  }}}}}},
}};

test('CDN failure preserves locally rendered operations and Execute buttons', async () => {
  const h = harness(true, async () => ({ok: true, status: 200, json: async () => schema, text: async () => '{"id":1}'}));
  await h.document.DOMContentLoaded();
  assert.equal(h.elements.operations.children.length, 2);
  const script = h.document.head.children[0];
  assert.equal(script.src, '/api/docs/assets/swagger-ui-bundle.js');
  script.onerror();
  assert.equal(h.elements['local-docs'].hidden, false);
  assert.match(h.elements['docs-status'].textContent, /CDN недоступен/);
  const operation = h.elements.operations.children[0];
  const button = operation.children.find(e => e.tag === 'button');
  await button.events.click();
  assert.equal(h.calls[1][0], '/api/runs/1/');
  assert.equal(button.disabled, false);
  assert.match(operation.children.find(e => e.tag === 'pre').textContent, /HTTP 200/);
  assert.match(operation.children.find(e => e.tag === 'pre').textContent, /"id": 1/);
});

test('schema HTTP failure is visible to user', async () => {
  const h = harness(true, async () => ({ok: false, status: 500}));
  await h.document.DOMContentLoaded();
  assert.match(h.elements['docs-status'].textContent, /HTTP 500/);
  assert.equal(h.document.head.children.length, 0);
});

test('Swagger receives same-origin schema, CSRF interceptor and disabled external validator', async () => {
  const h = harness(true, async () => ({ok: true, json: async () => schema}));
  await h.document.DOMContentLoaded();
  let options;
  h.window.SwaggerUIBundle = value => { options = value; value.onComplete(); };
  h.document.head.children[0].onload();
  const stylesheet = h.document.head.children[1];
  stylesheet.onload();
  assert.equal(options.url, '/api/schema/');
  assert.equal(options.validatorUrl, null);
  assert.equal(options.requestInterceptor, h.api.prepareRequest);
  assert.equal(h.elements['swagger-ui'].hidden, false);
});
