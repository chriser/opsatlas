// The control panel's own Tibi client (frontend/src/tibi/voice.ts), not its predecessor (audit F09): End, or a new
// Start, while a start is still under way never opens a stale conversation, re-enables the microphone or overwrites
// the current session. voice.ts is transpiled with the frontend's TypeScript; the browser and network are stubbed.
// Needs frontend/node_modules (CI runs it after the frontend build).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const ts = require(path.join(root, 'frontend/node_modules/typescript'));
const source = fs.readFileSync(path.join(root, 'frontend/src/tibi/voice.ts'), 'utf8').replace(/^import .*;\n/gm, '');
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;

function deferred() {
  let resolve;
  const promise = new Promise((r) => { resolve = r; });
  return { promise, resolve };
}

function load({ session, token, capture }) {
  // Each start's conversation request resolves separately: a list of deferreds, or one for every request.
  const sessions = Array.isArray(session) ? [...session] : null;
  const posts = [];
  const sockets = [];
  const stopped = [];
  const context = {
    record: () => {},
    signInToken: () => 'signed-in',
    getTibiServiceToken: () => token.promise,
    tibiServicePost: (url, body) => {
      posts.push(url);
      if (url !== '/api/interviews') return Promise.resolve({});
      return (sessions ? sessions.shift() : session).promise;
    },
    TurnTiming: class {},
  };
  globalThis.AudioContext = class {};
  globalThis.window = { setTimeout, clearTimeout, addEventListener: () => {}, AudioWorkletNode: class {} };
  globalThis.localStorage = { getItem: () => null, setItem: () => {} };
  globalThis.location = { protocol: 'http:', host: 'localhost' };
  globalThis.crypto ??= { randomUUID: () => 'id' };
  globalThis.WebSocket = class { static OPEN = 1; readyState = 0; constructor(url) { sockets.push(url); } close() {} send() {} };
  Object.defineProperty(globalThis, 'navigator', { configurable: true, writable: true, value: {
    mediaDevices: {
      getUserMedia: async () => {
        await capture.promise;
        return { getTracks: () => [{ stop: () => stopped.push('track'), onended: null }], getAudioTracks: () => [{ label: 'Jabra' }] };
      },
      enumerateDevices: async () => [],
      addEventListener: () => {},
    },
  } });
  const module = { exports: {} };
  new Function('exports', ...Object.keys(context), compiled)(module.exports, ...Object.values(context));
  const voice = new module.exports.TibiVoice();
  voice.audioOutput = async () => {};  // no audio graph in node
  return { voice, posts, sockets, stopped };
}

const settle = () => new Promise((r) => setTimeout(r, 10));
const options = { mode: 'chat', contributor: 'Chris', topic: '', voice: 'higgs', typed: true };

test('End while the conversation is being created: the late session never connects and is paused', async () => {
  const session = deferred(), token = deferred(), capture = deferred();
  capture.resolve();
  const { voice, posts, sockets } = load({ session, token, capture });
  const starting = voice.start(options);
  await settle();
  voice.end();
  session.resolve({ id: 'late-session', revision: 0 });
  token.resolve('t');
  await starting;
  assert.equal(voice.view.phase, 'closed');
  assert.equal(sockets.length, 0);
  assert.equal(voice.session, null);
  assert.ok(posts.includes('/api/interviews/late-session/pause'));
});

test('End while the service token is fetched: no socket is opened', async () => {
  const session = deferred(), token = deferred(), capture = deferred();
  capture.resolve();
  session.resolve({ id: 's1', revision: 0 });
  const { voice, sockets } = load({ session, token, capture });
  const starting = voice.start(options);
  await settle();
  voice.end();
  token.resolve('t');
  await starting;
  assert.equal(sockets.length, 0);
  assert.equal(voice.view.phase, 'closed');
});

test('End while the microphone is being granted: the microphone is released and nothing is created', async () => {
  const session = deferred(), token = deferred(), capture = deferred();
  session.resolve({ id: 's1', revision: 0 });
  token.resolve('t');
  const { voice, posts, sockets, stopped } = load({ session, token, capture });
  const starting = voice.start({ ...options, typed: false });
  await settle();
  voice.end();
  capture.resolve();
  await starting;
  assert.deepEqual(stopped, ['track']);
  assert.equal(voice.stream ?? null, null);
  assert.ok(!posts.includes('/api/interviews'));
  assert.equal(sockets.length, 0);
});

test('A new Start replaces a pending one: the stale session never overwrites the new one', async () => {
  const stale = deferred(), fresh = deferred(), token = deferred(), capture = deferred();
  capture.resolve();
  token.resolve('t');
  const { voice, posts, sockets } = load({ session: [stale, fresh], token, capture });
  const one = voice.start(options);
  await settle();
  voice.end();
  const two = voice.start(options);  // started again before the first request came back
  await settle();
  fresh.resolve({ id: 'fresh', revision: 0 });
  await settle();
  stale.resolve({ id: 'stale', revision: 0 });
  await Promise.all([one, two]);
  assert.equal(voice.session.id, 'fresh');
  assert.deepEqual(sockets, ['ws://localhost/services/tibi/api/conversation/fresh']);
  assert.ok(posts.includes('/api/interviews/stale/pause'));
});
