import assert from 'node:assert/strict';
import test from 'node:test';
import {renderEvents} from '../src/renderer.mjs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

test('renders unknown usage and a candidate-bound unapproved package', () => {
  const output = renderEvents([
    {version: 1, type: 'ready', state: {stage: 'contracted', ready: 1, active: 0,
      waiting: 0, completed: 0, usage_known: false}, task: {task_id: 'demo'}},
    {version: 1, type: 'transcript_item', item: {role: 'status', text: 'verified'}},
    {version: 1, type: 'package_ready', package: {head_revision: 'abc',
      verification_count: 1, findings_count: 0, approval_recorded: false}},
  ]);
  assert.match(output, /usage: unknown/);
  assert.match(output, /candidate: abc/);
  assert.match(output, /approval recorded: no/);
});

test('renders lifecycle and identity warnings', () => {
  const output = renderEvents([{version: 1, type: 'state_snapshot', state: {
    stage: 'authentication_required', authentication_required: true,
    candidate_stale: true, cancelled: false, ready: 0, active: 0, waiting: 1, completed: 1,
  }}]);
  assert.match(output, /AUTHENTICATION REQUIRED/);
  assert.match(output, /CANDIDATE STALE/);
});

test('rejects unversioned or authority-expanding events', () => {
  assert.throws(() => renderEvents([{type: 'approval_granted'}]), /unsupported backend event/);
});

test('frontend demo request carries no authority-bearing data', () => {
  const requestPath = fileURLToPath(new URL('../src/request-demo.mjs', import.meta.url));
  const request = JSON.parse(execFileSync(process.execPath, [requestPath], {encoding: 'utf8'}));
  assert.deepEqual(request, {version: 1, type: 'run_demo'});
});
