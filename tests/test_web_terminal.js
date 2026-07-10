const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('web/index.html', 'utf8');
assert.match(html, /\.term-content \{[^}]*padding: 10px 16px/);
assert.match(html, /\.ansi-line \{[^}]*overflow: hidden/);
const colorsStart = html.indexOf('const ANSI_COLORS =');
const colorsEnd = html.indexOf('\n};', colorsStart) + 3;
const rendererStart = html.indexOf('function trimAnsiLineEnd');
const rendererEnd = html.indexOf('function hostLabel', rendererStart);

assert.ok(colorsStart >= 0 && colorsEnd > colorsStart, 'ANSI color table not found');
assert.ok(rendererStart >= 0 && rendererEnd > rendererStart, 'ANSI renderer not found');

const sandbox = {};
vm.runInNewContext(`
${html.slice(colorsStart, colorsEnd)}
const TERMINAL_SEPARATOR_TOKEN = '\\uE000HERDR_SEPARATOR\\uE000';
${html.slice(rendererStart, rendererEnd)}
this.ansi256Color = ansi256Color;
this.ansiToHtml = ansiToHtml;
this.ansiLineBackground = ansiLineBackground;
this.ansiLineBackgrounds = ansiLineBackgrounds;
this.terminalHtml = terminalHtml;
`, sandbox);

assert.equal(sandbox.ansi256Color(6), '#1abc9c');
assert.equal(sandbox.ansi256Color(196), 'rgb(255,0,0)');
assert.equal(sandbox.ansi256Color(244), 'rgb(128,128,128)');

const tools = sandbox.ansiToHtml('\x1b[38;5;6mSearch\x1b[0m and \x1b[38;5;6mRead\x1b[0m');
assert.match(tools, /color:#1abc9c[^>]*>Search/);
assert.match(tools, /color:#1abc9c[^>]*>Read/);

const background = sandbox.ansiToHtml('\x1b[1;48;5;196mAlert\x1b[0m');
assert.match(background, /font-weight:700/);
assert.match(background, /background-color:rgb\(255,0,0\)/);

const explored = sandbox.terminalHtml('\x1b[1mExplored\x1b[0m');
assert.match(explored, /font-weight:700;color:#5fafff[^>]*>Explored/);

const prompt = sandbox.terminalHtml([
  '\x1b[48;2;61;64;64m› First prompt paragraph   \x1b[0m',
  '\r',
  '\x1b[48;2;61;64;64mSecond paragraph that wraps on a phone   \x1b[0m',
].join('\n'));
assert.equal(sandbox.ansiLineBackground('\x1b[48;2;61;64;64m› Prompt\x1b[0m'), 'rgb(61,64,64)');
assert.match(prompt, /class="ansi-line ansi-line-background" style="background-color:rgb\(61,64,64\)"/);
assert.equal((prompt.match(/class="ansi-line ansi-line-background"/g) || []).length, 3);
assert.doesNotMatch(prompt, /paragraph {3}/);

const separateBlocks = sandbox.ansiLineBackgrounds([
  '\x1b[48;5;1mFirst block\x1b[0m',
  '',
  'Normal output',
  '',
  '\x1b[48;5;1mSecond block\x1b[0m',
]);
assert.deepEqual(separateBlocks, ['#ff5f5f', '', '', '', '#ff5f5f']);

console.log('ANSI terminal renderer tests passed');
