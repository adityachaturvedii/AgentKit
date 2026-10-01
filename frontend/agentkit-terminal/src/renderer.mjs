/*
 * Adapted from HKUDS/OpenHarness StatusBar.tsx and TranscriptPane.tsx at
 * 9b2efd795c6aa09f88b0c257d269a9e518da6ae7. MIT License, Copyright (c) 2025
 * OpenHarness Contributors. See THIRD_PARTY_NOTICES.md and adaptation-map.json.
 */

const EVENT_TYPES = new Set([
  'ready', 'state_snapshot', 'transcript_item', 'package_ready', 'error', 'shutdown',
]);

function count(value) {
  return Number.isInteger(value) && value >= 0 ? String(value) : 'unknown';
}

export function renderEvents(events) {
  if (!Array.isArray(events) || events.length === 0) throw new Error('event stream is empty');
  let state = {};
  let task = null;
  const transcript = [];
  let packageSummary = null;
  for (const event of events) {
    if (!event || event.version !== 1 || !EVENT_TYPES.has(event.type)) {
      throw new Error('unsupported backend event');
    }
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
  const usage = state.usage_known
    ? `${state.input_tokens}↓ ${state.output_tokens}↑`
    : 'unknown';
  const flags = [];
  if (state.authentication_required) flags.push('AUTHENTICATION REQUIRED');
  if (state.candidate_stale) flags.push('CANDIDATE STALE');
  if (state.cancelled) flags.push('CANCELLED');
  const lines = [
    'Portable Agentkit',
    '────────────────────────────────────────────────────────────',
    `task: ${task?.task_id ?? 'unknown'} │ stage: ${state.stage ?? 'unknown'} │ usage: ${usage}`,
    `assignments: ${count(state.ready)} ready │ ${count(state.active)} active │ ${count(state.waiting)} waiting │ ${count(state.completed)} completed`,
  ];
  if (flags.length) lines.push(`attention: ${flags.join(' │ ')}`);
  if (state.blocker) lines.push(`blocker: ${state.blocker}`);
  lines.push('', 'Transcript');
  for (const item of transcript.slice(-24)) {
    if (!item || typeof item.role !== 'string' || typeof item.text !== 'string') {
      throw new Error('invalid transcript item');
    }
    lines.push(`${item.role}> ${item.text}`);
  }
  if (packageSummary) {
    lines.push('', `candidate: ${packageSummary.head_revision ?? 'unknown'}`,
      `verification: ${count(packageSummary.verification_count)} │ findings: ${count(packageSummary.findings_count)}`,
      `approval recorded: ${packageSummary.approval_recorded === true ? 'yes' : 'no'}`);
  }
  return `${lines.join('\n')}\n`;
}
