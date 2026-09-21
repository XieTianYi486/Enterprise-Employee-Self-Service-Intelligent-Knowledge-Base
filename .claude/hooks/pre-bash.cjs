// PreToolUse hook — 拦截 git commit / git push
// 强制所有代码提交必须通过 gitcommit-agent（/git-save 命令）
// 接收两个参数: tool_name 和 tool_input_json

const fs = require('fs');
const logFile = '.claude/hooks/debug.log';

function log(msg) {
  try { fs.appendFileSync(logFile, `[${new Date().toISOString()}] ${msg}\n`); } catch(e) {}
}

log('===== hook 被调用 =====');

// 从参数或环境变量获取 tool input
let command = '';

// 方式1: 命令行参数 (node script.cjs tool_name tool_input_json)
if (process.argv.length >= 4) {
  try {
    const input = JSON.parse(process.argv[3]);
    command = input.command || '';
  } catch(e) {}
}

// 方式2: 环境变量
if (!command) {
  command = process.env.CLAUDE_TOOL_INPUT || process.env.TOOL_INPUT || '';
}

// 方式3: stdin (带超时)
if (!command) {
  try {
    let input = '';
    process.stdin.on('data', chunk => { input += chunk; });
    setTimeout(() => {
      if (input) command = input;
    }, 500);
  } catch(e) {}
}

log(`argv count: ${process.argv.length}, argv: ${JSON.stringify(process.argv.slice(2))}`);
log(`command: "${command}"`);

const cmdLower = command.toLowerCase().trim();
const blockedPatterns = ['git commit', 'git push'];
const isBlocked = blockedPatterns.some(p => cmdLower.includes(p));

if (isBlocked && command) {
  log('BLOCKED');
  process.stdout.write(JSON.stringify({
    permission: 'deny',
    message: '🚫 请使用 /git-save 命令提交代码（会先自动运行测试和质量检查）'
  }));
  process.exit(0);
}

log('ALLOW');
process.stdout.write(JSON.stringify({ permission: 'allow' }));
process.exit(0);
