const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('web/index.html', 'utf8');
const start = html.indexOf('function activityMatchesSearch');
const end = html.indexOf('function activityColor', start);

assert.ok(start >= 0 && end > start, 'Activity search helper not found');

const sandbox = {};
vm.runInNewContext(`${html.slice(start, end)}\nthis.activityMatchesSearch = activityMatchesSearch;`, sandbox);

const activity = {
  summary: 'Approval accepted',
  kind: 'approval',
  status: 'confirmed',
  relay_label: 'Fedora',
  project: 'herdr-mobile-relay',
  agent: 'Codex',
  details: {choice: 'Approve once'},
};

assert.equal(sandbox.activityMatchesSearch(activity, ''), true);
assert.equal(sandbox.activityMatchesSearch(activity, 'fedora'), true);
assert.equal(sandbox.activityMatchesSearch(activity, 'herdr-mobile'), true);
assert.equal(sandbox.activityMatchesSearch(activity, 'approve once'), true);
assert.equal(sandbox.activityMatchesSearch(activity, 'missing'), false);

console.log('Activity search tests passed');
