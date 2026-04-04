const fs = require('fs/promises');
const fsSync = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');
const { runCommand } = require('../lib/exec');

function resolveCodexBin(env = process.env, platform = process.platform) {
  if (env.CODEX_BIN && String(env.CODEX_BIN).trim()) {
    return String(env.CODEX_BIN).trim();
  }

  return 'codex';
}

function getCodexCommandOptions(env = process.env, platform = process.platform) {
  if (platform === 'win32' && !(env.CODEX_BIN && String(env.CODEX_BIN).trim())) {
    return { shell: true };
  }

  return {};
}

function resolveCodexExecCommand(env = process.env, platform = process.platform) {
  if (env.CODEX_BIN && String(env.CODEX_BIN).trim()) {
    return {
      bin: String(env.CODEX_BIN).trim(),
      prefixArgs: ['exec'],
      options: {},
    };
  }

  if (platform === 'win32') {
    const codexJsPath = env.CODEX_JS_PATH || path.join(
      env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'),
      'npm',
      'node_modules',
      '@openai',
      'codex',
      'bin',
      'codex.js'
    );

    if (fsSync.existsSync(codexJsPath)) {
      return {
        bin: process.execPath,
        prefixArgs: [codexJsPath, 'exec'],
        options: { windowsHide: true },
      };
    }
  }

  return {
    bin: resolveCodexBin(env, platform),
    prefixArgs: ['exec'],
    options: {},
  };
}

function runExecCommand(bin, args, options = {}) {
  const { timeoutMs, ...spawnOptions } = options;

  return new Promise((resolve, reject) => {
    const child = spawn(bin, args, {
      env: process.env,
      stdio: ['pipe', 'pipe', 'pipe'],
      ...spawnOptions,
    });

    let stdout = '';
    let stderr = '';
    let timedOut = false;
    let timeoutId = null;

    if (timeoutMs && Number.isFinite(timeoutMs) && timeoutMs > 0) {
      timeoutId = setTimeout(() => {
        timedOut = true;
        child.kill('SIGTERM');
      }, timeoutMs);
    }

    child.stdin.end();
    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    child.on('error', (error) => {
      if (timeoutId) clearTimeout(timeoutId);
      reject(error);
    });

    child.on('close', (code, signal) => {
      if (timeoutId) clearTimeout(timeoutId);

      if (timedOut) {
        const wrapped = new Error(
          `Command timed out after ${timeoutMs}ms: ${bin} ${args.join(' ')}`
        );
        wrapped.code = 'ETIMEDOUT';
        wrapped.signal = signal;
        wrapped.stdout = stdout;
        wrapped.stderr = stderr;
        return reject(wrapped);
      }

      if (code === 0) {
        return resolve({ stdout, stderr });
      }

      const message = (stderr || stdout || `Command exited with code ${code}`).trim();
      const wrapped = new Error(`Command failed: ${bin} ${args.join(' ')}\n${message}`);
      wrapped.code = code;
      wrapped.signal = signal;
      wrapped.stdout = stdout;
      wrapped.stderr = stderr;
      return reject(wrapped);
    });
  });
}

function createCodexProvider(env = process.env) {
  const bin = resolveCodexBin(env);
  const commandOptions = getCodexCommandOptions(env);
  const execCommand = resolveCodexExecCommand(env);
  const defaultModel = env.CODEX_MODEL || 'gpt-5.4-mini';
  const reasoningEffort = env.CODEX_MODEL_REASONING_EFFORT || 'high';
  const workdir = env.CODEX_BRIDGE_WORKDIR || process.cwd();
  const execTimeoutMs = Number(env.CODEX_EXEC_TIMEOUT_MS || 120000);

  return {
    name: 'codex',
    providerLabel: 'a local Codex OAuth session',
    defaultModel,
    workdir,
    resolveModel(requestedModel) {
      return typeof requestedModel === 'string' && requestedModel.trim() ? requestedModel.trim() : defaultModel;
    },
    async runCompletion({ prompt, model }) {
      const tmpDir = await fs.mkdtemp(path.join(os.tmpdir(), 'codex-bridge-'));
      const outputFile = path.join(tmpDir, 'last-message.txt');

      const args = [
        ...execCommand.prefixArgs,
        '-c',
        `model_reasoning_effort="${reasoningEffort}"`,
        '--skip-git-repo-check',
        '--ephemeral',
        '-C',
        workdir,
        '-m',
        model,
        '-o',
        outputFile,
        prompt,
      ];

      try {
        const { stdout = '' } = await runExecCommand(execCommand.bin, args, {
          ...execCommand.options,
          timeoutMs: Number.isFinite(execTimeoutMs) && execTimeoutMs > 0 ? execTimeoutMs : undefined,
        });

        if (fsSync.existsSync(outputFile)) {
          const content = await fs.readFile(outputFile, 'utf8');
          return content.trim();
        }

        if (stdout.trim()) {
          return stdout.trim();
        }

        throw new Error('Codex CLI completed without writing a response payload.');
      } finally {
        await fs.rm(tmpDir, { recursive: true, force: true });
      }
    },
    async getHealth() {
      let cliAvailable = false;
      let loginStatus = 'unknown';

      try {
        await runCommand(bin, ['--version'], commandOptions);
        cliAvailable = true;
      } catch {
        cliAvailable = false;
      }

      try {
        const { stdout = '', stderr = '' } = await runCommand(bin, ['login', 'status'], commandOptions);
        loginStatus = stdout.trim() || stderr.trim() || 'unknown';
      } catch {
        loginStatus = 'not logged in';
      }

      const credentialsPath = path.join(os.homedir(), '.codex');

      return {
        cliAvailable,
        loginStatus,
        credentialsDirectoryPresent: fsSync.existsSync(credentialsPath),
        workdir,
        execTimeoutMs,
      };
    },
    getStartupSummary() {
      const credentialsPath = path.join(os.homedir(), '.codex');
      return {
        bin,
        defaultModel,
        reasoningEffort,
        workdir,
        execTimeoutMs,
        authHint: fsSync.existsSync(credentialsPath) ? 'credentials directory present' : 'credentials directory missing',
      };
    },
  };
}

module.exports = {
  createCodexProvider,
  getCodexCommandOptions,
  resolveCodexExecCommand,
  resolveCodexBin,
};
