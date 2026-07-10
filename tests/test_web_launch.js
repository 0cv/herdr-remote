const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('web/index.html', 'utf8');
const start = html.indexOf('function launchNamePart');
const end = html.indexOf('function updateLaunchName', start);

assert.ok(start >= 0 && end > start, 'Launch-name helpers not found');

const sandbox = {};
vm.runInNewContext(`
${html.slice(start, end)}
this.suggestedLaunchName = suggestedLaunchName;
`, sandbox);

assert.equal(
  sandbox.suggestedLaunchName('/home/me/Development/herdr-mobile-relay', 'codex'),
  'herdr-mobile-relay-codex'
);
assert.equal(sandbox.suggestedLaunchName('/Users/me/Projects/Málaga App', 'claude'), 'malaga-app-claude');
assert.equal(sandbox.suggestedLaunchName('/', 'opencode'), 'project-opencode');

const longName = sandbox.suggestedLaunchName(`/home/me/${'project'.repeat(12)}`, 'codex');
assert.ok(longName.length <= 48);
assert.match(longName, /-codex$/);

const cwdField = html.indexOf('<div class="field-label" id="launchCwdLabel">Working Directory</div>');
const nameField = html.indexOf('<label for="launchName">Name</label>');
assert.ok(cwdField >= 0 && cwdField < nameField, 'Working Directory must appear before Name');
assert.match(html, /<input id="launchCwd" type="hidden" \/>/);
assert.match(html, /id="launchDirectoryUp"[^>]*openParentLaunchDirectory/);
assert.match(html, /id="launchDirectoryList"/);
assert.match(html, /The folder shown above is used\. Tap a subfolder to open it\./);
assert.match(html, /Update and restart this computer’s relay to browse directories\./);
assert.match(html, /Sent to the agent as its first prompt after it starts\./);

console.log('Agent launch form tests passed');
