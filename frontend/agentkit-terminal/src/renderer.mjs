/*
 * Adapted from HKUDS/OpenHarness StatusBar.tsx and TranscriptPane.tsx at
 * 9b2efd795c6aa09f88b0c257d269a9e518da6ae7. MIT License, Copyright (c) 2025
 * OpenHarness Contributors. See THIRD_PARTY_NOTICES.md and adaptation-map.json.
 */

const EVENT_TYPES = new Set([
  'ready', 'state_snapshot', 'transcript_item', 'package_ready', 'error', 'shutdown',
]);
const EVENT_KEYS = new Set(['version', 'type', 'state', 'task', 'item', 'package', 'message']);
const STATE_KEYS = new Set([
  'stage', 'ready', 'active', 'waiting', 'completed', 'input_tokens', 'output_tokens',
  'usage_known', 'authentication_required', 'candidate_stale', 'cancelled', 'blocker',
  'approval_recorded', 'next_action', 'attention', 'routing',
  'candidate',
]);
const TASK_KEYS = new Set(['task_id', 'state', 'objective', 'next_action', 'head_revision']);
const PACKAGE_KEYS = new Set([
  'task_id', 'status', 'branch', 'base_revision', 'head_revision',
  'verification_count', 'findings_count', 'approval_recorded',
]);
const ROUTE_KEYS = new Set(['role', 'provider', 'reason']);
const CANDIDATE_KEYS = new Set(['branch', 'base_revision', 'head_revision']);
const TRANSCRIPT_ROLES = new Set(['system', 'status', 'assistant', 'log']);

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function hasOnlyKeys(value, allowed) {
  return Object.keys(value).every((key) => allowed.has(key));
}

function textValue(value, name, {nullable = false, limit = 4096} = {}) {
  if (nullable && (value === null || value === undefined)) return null;
  if (typeof value !== 'string' || value.length > limit ||
      /[\u0000-\u0008\u000b-\u001f\u007f]/u.test(value)) {
    throw new Error(`invalid ${name}`);
  }
  return value;
}

function optionalText(value, name, limit = 4096) {
  return textValue(value, name, {nullable: true, limit});
}

function nonnegativeInteger(value, name, {optional = true} = {}) {
  if (optional && (value === null || value === undefined)) return null;
  if (!Number.isSafeInteger(value) || value < 0) throw new Error(`invalid ${name}`);
  return value;
}

function optionalBoolean(value, name) {
  if (value === undefined) return false;
  if (typeof value !== 'boolean') throw new Error(`invalid ${name}`);
  return value;
}

function validateTask(task) {
  if (task === null || task === undefined) return null;
  if (!isRecord(task) || !hasOnlyKeys(task, TASK_KEYS) || Object.keys(task).length !== TASK_KEYS.size) {
    throw new Error('invalid task snapshot');
  }
  for (const key of ['task_id', 'state', 'objective']) {
    if (Object.hasOwn(task, key)) optionalText(task[key], `task ${key}`, key === 'objective' ? 4096 : 512);
  }
  for (const key of ['next_action', 'head_revision']) {
    if (Object.hasOwn(task, key)) optionalText(task[key], `task ${key}`, 4096);
  }
  return task;
}

function validateTranscriptItem(item) {
  const itemKeys = new Set(['role', 'text']);
  if (!isRecord(item) || !hasOnlyKeys(item, itemKeys) ||
      Object.keys(item).length !== 2 || !TRANSCRIPT_ROLES.has(item.role)) {
    throw new Error('invalid transcript item');
  }
  textValue(item.text, 'transcript text', {limit: 8192});
  return item;
}

function validateRoute(route) {
  if (!isRecord(route) || !hasOnlyKeys(route, ROUTE_KEYS) || Object.keys(route).length !== 3) {
    throw new Error('invalid routing entry');
  }
  textValue(route.role, 'routing role', {limit: 128});
  textValue(route.provider, 'routing provider', {limit: 128});
  textValue(route.reason, 'routing reason', {limit: 4096});
  return route;
}

function validateState(state) {
  if (state === null || state === undefined) return {};
  if (!isRecord(state) || !hasOnlyKeys(state, STATE_KEYS)) throw new Error('invalid workflow state');
  optionalText(state.stage, 'workflow stage', 256);
  optionalText(state.blocker, 'workflow blocker');
  optionalText(state.next_action, 'workflow next action');
  optionalText(state.attention, 'workflow attention');
  for (const key of ['ready', 'active', 'waiting', 'completed', 'input_tokens', 'output_tokens']) {
    nonnegativeInteger(state[key], key);
  }
  for (const key of ['usage_known', 'authentication_required', 'candidate_stale', 'cancelled']) {
    optionalBoolean(state[key], key);
  }
  if (state.approval_recorded !== undefined && state.approval_recorded !== false) {
    throw new Error('authority-expanding backend event');
  }
  if (state.usage_known === true &&
      (nonnegativeInteger(state.input_tokens, 'input_tokens') === null ||
       nonnegativeInteger(state.output_tokens, 'output_tokens') === null)) {
    throw new Error('known usage requires token counts');
  }
  if (state.routing !== undefined) {
    if (!Array.isArray(state.routing) || state.routing.length > 16) throw new Error('invalid routing');
    state.routing.forEach(validateRoute);
  }
  if (state.candidate !== undefined && state.candidate !== null) {
    if (!isRecord(state.candidate) || !hasOnlyKeys(state.candidate, CANDIDATE_KEYS) ||
        Object.keys(state.candidate).length !== CANDIDATE_KEYS.size) {
      throw new Error('invalid candidate summary');
    }
    for (const key of CANDIDATE_KEYS) {
      if (Object.hasOwn(state.candidate, key)) optionalText(state.candidate[key], `candidate ${key}`, 512);
    }
  }
  return state;
}

function validatePackage(value) {
  if (value === null || value === undefined) return null;
  if (!isRecord(value) || !hasOnlyKeys(value, PACKAGE_KEYS)) throw new Error('invalid package summary');
  for (const key of ['task_id', 'status', 'branch', 'base_revision', 'head_revision']) {
    if (Object.hasOwn(value, key)) optionalText(value[key], `package ${key}`, 512);
  }
  nonnegativeInteger(value.verification_count, 'verification_count');
  nonnegativeInteger(value.findings_count, 'findings_count');
  if (value.approval_recorded !== false) throw new Error('authority-expanding backend event');
  return value;
}

function validateEvent(event) {
  if (!isRecord(event) || event.version !== 1 || !EVENT_TYPES.has(event.type) ||
      !hasOnlyKeys(event, EVENT_KEYS)) {
    throw new Error('unsupported backend event');
  }
  if (event.message !== undefined) textValue(event.message, 'event message');
  if (event.state !== undefined) validateState(event.state);
  if (event.task !== undefined) validateTask(event.task);
  if (event.item !== undefined && event.item !== null) validateTranscriptItem(event.item);
  if (event.package !== undefined) validatePackage(event.package);
  return event;
}

function count(value) {
  return Number.isSafeInteger(value) && value >= 0 ? String(value) : 'unknown';
}

function appendTranscript(lines, item) {
  for (const line of item.text.split(/\r?\n/u)) lines.push(`${item.role}> ${line}`);
}

export function renderEvents(events) {
  if (!Array.isArray(events) || events.length === 0) throw new Error('event stream is empty');
  let state = {};
  let task = null;
  const transcript = [];
  let packageSummary = null;
  for (const rawEvent of events) {
    const event = validateEvent(rawEvent);
    if (event.type === 'ready' || event.type === 'state_snapshot') {
      state = event.state ?? {};
      task = event.task ?? task;
      if (event.item) transcript.push(event.item);
    } else if (event.type === 'transcript_item' && event.item) {
      transcript.push(event.item);
    } else if (event.type === 'package_ready') {
      packageSummary = event.package ?? null;
      if (event.message) transcript.push({role: 'status', text: event.message});
    } else if (event.message) {
      transcript.push({role: event.type === 'error' ? 'system' : 'status', text: event.message});
    }
  }
  const usage = state.usage_known === true
    ? `${state.input_tokens}↓ ${state.output_tokens}↑`
    : 'unknown';
  const attention = [];
  if (state.authentication_required) attention.push('AUTHENTICATION REQUIRED');
  if (state.candidate_stale) attention.push('CANDIDATE STALE');
  if (state.cancelled) attention.push('CANCELLED');
  if (state.attention) attention.push(state.attention);
  const lines = [
    'AgentKit',
    '─'.repeat(60),
    `task: ${task?.task_id ?? 'unknown'} │ stage: ${state.stage ?? task?.state ?? 'unknown'} │ usage: ${usage}`,
    `assignments: ${count(state.ready)} ready │ ${count(state.active)} active │ ${count(state.waiting)} waiting │ ${count(state.completed)} completed`,
  ];
  if (state.next_action ?? task?.next_action) lines.push(`next action: ${state.next_action ?? task.next_action}`);
  if (attention.length) lines.push(`attention: ${attention.join(' │ ')}`);
  if (state.blocker) lines.push(`blocker: ${state.blocker}`);
  if (state.candidate) {
    lines.push(`candidate: ${state.candidate.head_revision ?? 'unknown'} │ branch: ${state.candidate.branch ?? 'unknown'} │ base: ${state.candidate.base_revision ?? 'unknown'}`);
  }
  if (state.routing?.length) {
    lines.push('', 'Routing');
    for (const route of state.routing) {
      lines.push(`${route.role}: ${route.provider}`, `  reason: ${route.reason}`);
    }
  }
  lines.push('', 'Transcript');
  for (const item of transcript.slice(-24)) appendTranscript(lines, item);
  if (packageSummary) {
    lines.push('', `candidate: ${packageSummary.head_revision ?? 'unknown'}`,
      `package: ${packageSummary.task_id ?? task?.task_id ?? 'unknown'} │ status: ${packageSummary.status ?? state.stage ?? 'unknown'} │ branch: ${packageSummary.branch ?? 'unknown'} │ base: ${packageSummary.base_revision ?? 'unknown'}`,
      `verification: ${count(packageSummary.verification_count)} │ findings: ${count(packageSummary.findings_count)}`,
      'approval recorded: no');
  }
  return `${lines.join('\n')}\n`;
}
