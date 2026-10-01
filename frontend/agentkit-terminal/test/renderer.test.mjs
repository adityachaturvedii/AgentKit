import assert from 'node:assert/strict';
import test from 'node:test';
import {renderEvents} from '../src/renderer.mjs';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

test('renders unknown usage and a candidate-bound unapproved package', () => {
  const output = renderEvents([
    {version: 1, type: 'ready', state: {stage: 'contracted', ready: 1, active: 0,
      waiting: 0, completed: 0, usage_known: false}, task: {task_id: 'demo',
        state: 'contracted', objective: 'Demo', next_action: null, head_revision: null}},
    {version: 1, type: 'transcript_item', item: {role: 'status', text: 'verified'}},
    {version: 1, type: 'package_ready', package: {head_revision: 'abc',
      verification_count: 1, findings_count: 0, approval_recorded: false}},
  ]);
  assert.match(output, /^AgentKit$/m);
  assert.doesNotMatch(output, /Portable AgentKit/i);
  assert.match(output, /usage: unknown/);
  assert.match(output, /candidate: abc/);
  assert.match(output, /approval recorded: no/);
});

test('renders the projected exact candidate and package identity', () => {
  const output = renderEvents([
    {version: 1, type: 'state_snapshot', state: {stage: 'awaiting_pr_approval',
      usage_known: false, approval_recorded: false, candidate: {
        branch: 'agentkit/task-7', base_revision: 'base123', head_revision: 'head456',
      }}, task: {task_id: 'task-7', state: 'awaiting_pr_approval',
        objective: 'Deliver task', next_action: 'review package', head_revision: 'head456'}},
    {version: 1, type: 'package_ready', package: {task_id: 'task-7',
      status: 'awaiting_pr_approval', branch: 'agentkit/task-7', base_revision: 'base123',
      head_revision: 'head456', verification_count: 2, findings_count: 0,
      approval_recorded: false}},
  ]);
  assert.match(output, /candidate: head456 │ branch: agentkit\/task-7 │ base: base123/);
  assert.match(output, /package: task-7 │ status: awaiting_pr_approval │ branch: agentkit\/task-7 │ base: base123/);
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

test('renders general workflow status, next action, attention, assignments, and routing', () => {
  const output = renderEvents([{version: 1, type: 'state_snapshot', task: {
    task_id: 'delivery-7', state: 'blocked', objective: 'Deliver change',
    next_action: 'inspect failed assignment', head_revision: 'deadbeef',
  }, state: {
    stage: 'blocked', next_action: 'inspect failed assignment',
    attention: 'review needs operator attention', blocker: 'verification failed',
    ready: 1, active: 2, waiting: 3, completed: 4, usage_known: true,
    input_tokens: 120, output_tokens: 30, approval_recorded: false,
    routing: [
      {role: 'implementer', provider: 'codex', reason: 'selected for owned-code capability'},
      {role: 'reviewer', provider: 'claude', reason: 'independent review provider'},
    ],
  }}]);
  assert.match(output, /task: delivery-7 │ stage: blocked │ usage: 120↓ 30↑/);
  assert.match(output, /assignments: 1 ready │ 2 active │ 3 waiting │ 4 completed/);
  assert.match(output, /next action: inspect failed assignment/);
  assert.match(output, /attention: review needs operator attention/);
  assert.match(output, /blocker: verification failed/);
  assert.match(output, /implementer: codex\n  reason: selected for owned-code capability/);
  assert.match(output, /reviewer: claude\n  reason: independent review provider/);
});

test('equivalent final snapshots render the same status regardless of preceding snapshots', () => {
  const finalEvent = {version: 1, type: 'state_snapshot', task: {
    task_id: 'same', state: 'awaiting_pr_approval', objective: 'Same status',
    next_action: 'review package', head_revision: 'abc',
  }, state: {
    stage: 'awaiting_pr_approval', next_action: 'review package', ready: 0,
    active: 0, waiting: 0, completed: 2, usage_known: false,
    approval_recorded: false, routing: [],
  }};
  const initialEvent = {version: 1, type: 'ready', task: {
    task_id: 'same', state: 'contracted', objective: 'Same status',
    next_action: 'start', head_revision: null,
  }, state: {
    stage: 'contracted', ready: 2, active: 0, waiting: 0, completed: 0,
    usage_known: false, approval_recorded: false,
  }};
  assert.equal(renderEvents([initialEvent, finalEvent]), renderEvents([finalEvent]));
});

test('rejects unversioned or authority-expanding events', () => {
  assert.throws(() => renderEvents([{type: 'approval_granted'}]), /unsupported backend event/);
  assert.throws(() => renderEvents([{version: 1, type: 'state_snapshot',
    approval: true}]), /unsupported backend event/);
  assert.throws(() => renderEvents([{version: 1, type: 'state_snapshot', state: {
    approval_recorded: true,
  }}]), /authority-expanding backend event/);
  assert.throws(() => renderEvents([{version: 1, type: 'package_ready', package: {
    head_revision: 'abc', verification_count: 1, findings_count: 0,
    approval_recorded: true,
  }}]), /authority-expanding backend event/);
  assert.throws(() => renderEvents([{version: 1, type: 'state_snapshot', state: {
    routing: [{role: 'reviewer', provider: 'claude', reason: 'review', permission: true}],
  }}]), /invalid routing entry/);
});

test('rejects terminal-control injection and prefixes every transcript line', () => {
  assert.throws(() => renderEvents([{version: 1, type: 'transcript_item', item: {
    role: 'status', text: '\u001b[2Jforged status',
  }}]), /invalid transcript text/);
  const output = renderEvents([{version: 1, type: 'transcript_item', item: {
    role: 'status', text: 'first\nattention: ordinary transcript text',
  }}]);
  assert.match(output, /status> first\nstatus> attention: ordinary transcript text/);
});

test('frontend demo request carries no authority-bearing data', () => {
  const requestPath = fileURLToPath(new URL('../src/request-demo.mjs', import.meta.url));
  const request = JSON.parse(execFileSync(process.execPath, [requestPath], {encoding: 'utf8'}));
  assert.deepEqual(request, {version: 1, type: 'run_demo'});
});
