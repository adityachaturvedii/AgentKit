/* Strict one-shot event renderer; never launches a backend or installs packages. */
import {readFile} from 'node:fs/promises';
import {renderEvents} from './renderer.mjs';

const path = process.argv[2];
if (!path) throw new Error('event stream path is required');
const raw = await readFile(path);
if (raw.byteLength > 1024 * 1024) throw new Error('event stream exceeds 1 MiB');
const events = raw.toString('utf8').split('\n').filter(Boolean).map((line) => {
  if (Buffer.byteLength(line, 'utf8') > 65536) throw new Error('event exceeds 64 KiB');
  return JSON.parse(line);
});
process.stdout.write(renderEvents(events));
