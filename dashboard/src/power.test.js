import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { runtime, powerLabel, canOperate } from './power.js';
import fs from 'node:fs';
import { build } from 'esbuild';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

test('actual operations components render generator, recovery, labels and errors', async () => {
  const outfile = path.resolve('.npm-cache/operations-test.mjs');
  await build({ entryPoints: ['src/pages/Operations.jsx'], outfile, bundle: true, platform: 'node', format: 'esm',
    external: ['react', 'react-dom'], define: { 'import.meta.env': '{}' } });
  const { OperationsDetails } = await import(pathToFileURL(outfile));
  const workload = { job_id: 'training', name: 'ML Training', criticality: 'CHECKPOINTABLE', status: 'deferred',
    last_power_action: 'CHECKPOINT_AND_DEFER', execution_status: 'SIMULATED_CONFIRMED', estimated_power_kw: 18,
    remaining_runtime_s: 14400, request: { deadline: '2026-10-10T19:00:00Z' } };
  const facility = { display_name: 'Demo facility', facility_id: 'demo', power_state: 'GENERATOR', generator_capacity_kw: 60,
    base_load_kw: 5, recovery_status: 'GENERATOR', recovery_hysteresis_s: 30, metrics: { baseline_it_kw: 55,
      post_decision_it_kw: 27, deferred_it_kw: 28, deferred_it_kwh: 42, demand_reduction_pct: 50.9, reduced_demand_s: 5400 },
    latest_decisions: [{ job_id: 'training', reason: 'Deadline slack permits deferral', deadline_feasible: true }] };
  let html = renderToStaticMarkup(React.createElement(OperationsDetails, { data: { facility, workloads: [workload] } }));
  for (const text of ['Generator backup', 'SIMULATED', 'MODELED', '55', '27', '28', '42', 'Deadline slack', 'no AWS process was paused']) assert.ok(html.includes(text), text);
  html = renderToStaticMarkup(React.createElement(OperationsDetails, { data: { facility: { ...facility, power_state: 'GRID_RECOVERY', recovery_status: 'WAITING_FOR_STABLE_GRID' }, workloads: [workload] } }));
  assert.ok(html.includes('Grid recovery'));
  assert.ok(html.includes('WAITING_FOR_STABLE_GRID'));
  const feedback = path.resolve('.npm-cache/feedback-test.mjs');
  await build({ entryPoints: ['src/pages/common.jsx'], outfile: feedback, bundle: true, platform: 'node', format: 'esm', external: ['react'] });
  const { ErrorBox } = await import(pathToFileURL(feedback));
  assert.ok(renderToStaticMarkup(React.createElement(ErrorBox, { error: new Error('API unavailable') })).includes('API unavailable'));
});

test('generator and recovery have readable distinct status labels', () => {
  for (const state of ['GRID', 'GENERATOR', 'GRID_RECOVERY', 'BATTERY_TRANSITION']) {
    const html = renderToStaticMarkup(React.createElement('span', null, powerLabel(state)));
    assert.ok(html.includes(powerLabel(state)));
  }
  assert.equal(runtime(5400), '90 min');
  assert.equal(runtime(null), 'Continuous');
});

test('simulator controls are shown only for unexpired platform-leads tokens', () => {
  const token = (claims) => `header.${btoa(JSON.stringify(claims))}.signature`;
  assert.equal(canOperate(token({ 'cognito:groups': ['platform-leads'], exp: 200 }), 100000), true);
  assert.equal(canOperate(token({ 'cognito:groups': ['viewers'], exp: 200 }), 100000), false);
  assert.equal(canOperate(token({ 'cognito:groups': ['platform-leads'], exp: 50 }), 100000), false);
  assert.equal(canOperate('invalid'), false);
});

test('operations navigation and essential simulation/error controls remain integrated', () => {
  const app = fs.readFileSync(new URL('./App.jsx', import.meta.url), 'utf8');
  const page = fs.readFileSync(new URL('./pages/Operations.jsx', import.meta.url), 'utf8');
  assert.ok(app.includes('["operations", "Power & Operations"]'));
  for (const label of ['SIMULATED', 'MODELED', 'ErrorBox', 'Reset demo', 'Restore grid', 'Confirm stable grid', 'platform-leads', 'aria-live']) assert.ok(page.includes(label), label);
  assert.ok(page.includes('api.power('));
  assert.ok(page.includes('api.facility('));
});
