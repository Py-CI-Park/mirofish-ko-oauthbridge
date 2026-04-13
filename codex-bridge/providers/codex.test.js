const test = require('node:test');
const assert = require('node:assert/strict');

const {
  getCodexCommandOptions,
  resolveCodexBin,
  resolveCodexExecCommand,
} = require('./codex');

test('resolveCodexBin uses codex by default', () => {
  assert.equal(resolveCodexBin({}, 'win32'), 'codex');
});

test('resolveCodexBin uses codex on non-Windows by default', () => {
  assert.equal(resolveCodexBin({}, 'linux'), 'codex');
});

test('resolveCodexBin respects CODEX_BIN override', () => {
  assert.equal(resolveCodexBin({ CODEX_BIN: 'custom-codex' }, 'win32'), 'custom-codex');
});

test('getCodexCommandOptions enables shell on Windows for npm shim lookup', () => {
  assert.deepEqual(getCodexCommandOptions({}, 'win32'), { shell: true });
});

test('getCodexCommandOptions keeps direct exec on non-Windows', () => {
  assert.deepEqual(getCodexCommandOptions({}, 'linux'), {});
});

test('resolveCodexExecCommand uses node + codex.js on Windows by default', () => {
  const command = resolveCodexExecCommand({
    APPDATA: String.raw`C:\Users\parkc\AppData\Roaming`,
  }, 'win32');

  assert.match(command.bin, /node(\.exe)?$/i);
  assert.match(command.prefixArgs[0], /@openai\\codex\\bin\\codex\.js$/i);
  assert.equal(command.prefixArgs[1], 'exec');
});
