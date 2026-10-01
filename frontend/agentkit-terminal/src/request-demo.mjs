/*
 * R0 frontend command adapter. Derived from the request-writing boundary in
 * OpenHarness useBackendSession.ts; it emits one fixed, versioned command and
 * cannot carry approval, permission, prompt, path, or provider data.
 */
process.stdout.write(`${JSON.stringify({version: 1, type: 'run_demo'})}\n`);
