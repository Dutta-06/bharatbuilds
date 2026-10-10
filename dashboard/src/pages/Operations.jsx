import React, { useEffect, useState } from 'react';
import { api } from '../api.js';
import { signIn } from './Policies.jsx';
import { Empty, ErrorBox, Loading, PageHead, Readout, Status } from './common.jsx';
import { runtime, powerLabel, canOperate } from '../power.js';

const LOCAL = import.meta.env.VITE_DG_LOCAL_SIMULATION === 'true' &&
  ['localhost', '127.0.0.1'].includes(window.location.hostname) &&
  ['localhost', '127.0.0.1'].includes(new URL(api.base).hostname);
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID;

export default function Operations() {
  const [id, setId] = useState('demo-delhi-01');
  const [facilities, setFacilities] = useState([]);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [token, setToken] = useState('');
  const [credentials, setCredentials] = useState({ email: '', password: '' });
  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      try {
        const list = await api.facilities();
        const next = list.some((f) => f.facility_id === id) ? await api.facility(id) : null;
        if (alive) { setFacilities(list); setData(next); setError(null); }
      } catch (err) { if (alive) setError(err); }
      finally { if (alive) setLoading(false); }
    };
    setLoading(true); refresh();
    const timer = setInterval(refresh, 3000);
    return () => { alive = false; clearInterval(timer); };
  }, [id]);

  const operate = async (body) => {
    setBusy(true); setError(null); setMessage('Sending telemetry…');
    try {
      const result = await api.power(id, body, token);
      if (result.status === 202) {
        setMessage('IoT Core accepted telemetry. Waiting for confirmed facility state…');
        let confirmed = false;
        for (let n = 0; n < 30; n++) {
          await new Promise((resolve) => setTimeout(resolve, 1000));
          const next = await api.facility(id);
          setData(next);
          if (next.facility.last_event_id === result.body.event_id) { confirmed = true; break; }
        }
        if (!confirmed) throw new Error(`Telemetry ${result.body.event_id} remains pending. Check ingestion logs before retrying.`);
      }
      setData(await api.facility(id));
      setFacilities(await api.facilities());
      setMessage('Facility state and scheduling decisions persisted.');
    } catch (err) { setError(err); setMessage('Action was not confirmed.'); }
    finally { setBusy(false); }
  };
  const f = data?.facility;
  const authorized = LOCAL || canOperate(token);
  return <>
    <PageHead eyebrow="Tidewise · DG-Shift capability" title="Power & Operations">
      Protect critical services during generator backup, defer eligible work, and recover within deadlines.
    </PageHead>
    <ErrorBox error={error} />
    {loading && <Loading />}
    <div className="banner warn" role="note">Facility execution is <strong>SIMULATED</strong>. Demand is <strong>MODELED</strong>.
      This monitored site is not an AWS region. Normal cloud scheduling remains independent.</div>
    <div className="ops-controls panel stack">
      {facilities.length > 0 && <div className="field"><label className="lbl" htmlFor="facility">Monitored facility</label>
        <select id="facility" value={id} onChange={(e) => setId(e.target.value)}>
          {facilities.map((site) => <option key={site.facility_id} value={site.facility_id}>{site.display_name}</option>)}
        </select></div>}
      {!authorized && CLIENT_ID && <form className="row" onSubmit={async (e) => {
        e.preventDefault(); setBusy(true); setError(null);
        try { setToken(await signIn(credentials.email, credentials.password)); setCredentials({ email: '', password: '' }); }
        catch (err) { setError(err); } finally { setBusy(false); }
      }}>
        <label>Email <input type="email" autoComplete="username" required value={credentials.email} onChange={(e) => setCredentials({ ...credentials, email: e.target.value })} /></label>
        <label>Password <input type="password" autoComplete="current-password" required value={credentials.password} onChange={(e) => setCredentials({ ...credentials, password: e.target.value })} /></label>
        <button className="btn" disabled={busy}>Sign in</button>
      </form>}
      {!authorized && <p className="small muted">Read-only view. Simulator controls require platform-leads sign-in.</p>}
      {authorized && <div className="row ops-buttons">
        <button className="btn" disabled={busy} onClick={() => operate({ operation: 'reset' })}>Reset demo</button>
        <button className="btn" disabled={busy || f?.power_state !== 'GRID'} onClick={() => operate({ power_state: 'BATTERY_TRANSITION' })}>Grid failure</button>
        <button className="primary" disabled={busy || !['GRID', 'BATTERY_TRANSITION'].includes(f?.power_state)} onClick={() => operate({ power_state: 'GENERATOR' })}>Activate generator</button>
        <button className="btn" disabled={busy || f?.power_state !== 'GENERATOR'} onClick={() => operate({ advance_s: 5400 })}>Advance 90 minutes</button>
        <button className="btn" disabled={busy || !['GENERATOR', 'BATTERY_TRANSITION'].includes(f?.power_state)} onClick={() => operate({ power_state: 'GRID_RECOVERY' })}>Restore grid</button>
        <button className="btn" disabled={busy || f?.power_state !== 'GRID_RECOVERY'} onClick={() => operate({ advance_s: 30 })}>Confirm stable grid (+30s)</button>
      </div>}
      <p className="small" role="status" aria-live="polite">{message}</p>
    </div>
    {!loading && !data && !error && <Empty title="No demo facility yet">A platform lead can reset the demo to provision all six workloads.</Empty>}
    {data && <OperationsDetails data={data} />}
  </>;
}

export function OperationsDetails({ data }) {
  const f = data.facility;
  const m = f.metrics;
  const decisions = new Map((f.latest_decisions || []).map((d) => [d.job_id, d]));
  return <>

      <section className="panel ops-overview" aria-label="Facility overview">
        <div><h2>{f.display_name}</h2><Status value={powerLabel(f.power_state)} /> <span className="tag">SIMULATED SOURCE</span>
          <p className="small">{f.facility_id} · generator capacity {f.generator_capacity_kw} kW · base load assumption {f.base_load_kw} kW (excluded from IT metrics)</p>
          <p className="small muted">Last telemetry: {f.last_observed_at} · scenario time: {f.simulation_time} · decision version {f.version}</p></div>
        <div><h3>Recovery</h3><p role="status">{f.recovery_status}</p>
          <p className="small">Stable-grid hysteresis: {f.recovery_hysteresis_s} seconds (demo setting).</p></div>
      </section>
      {m && <p className="eyebrow">MODELED IT demand · {m.basis || 'SIMULATED'} lifecycle</p>}
      {m && <section className="ops-metrics" aria-label="Modeled IT demand">
        <Readout label="Baseline IT demand" value={m.baseline_it_kw} unit="kW" />
        <Readout label="Post-decision demand" value={m.post_decision_it_kw} unit="kW">{m.demand_reduction_pct}% modeled demand reduction</Readout>
        <Readout label="Deferred IT demand" value={m.deferred_it_kw} unit="kW" />
        <Readout label="Generator-period demand deferred" value={m.deferred_it_kwh} unit="kWh">{runtime(m.reduced_demand_s)} of reduced demand</Readout>
      </section>}
      <p className="small muted">Deferred computing moves to a later time. These figures are not measured generator output or diesel/pollution savings.
        {f.fuel_estimate?.status === 'MODELED' ? <> Conditional fuel rate: {f.fuel_estimate.litres_per_hour} litres/hour MODELED; source: {f.fuel_estimate.source}. Manufacturer conditions must apply; this is not measured fuel savings.</> : <> Diesel estimate: UNAVAILABLE — {f.fuel_estimate?.reason || 'no sourced generator fuel curve'}.</>} Tidewise water/carbon receipts remain separate.</p>
      <div className="panel tight scroll"><table>
        <caption className="section-title">Facility workloads · simulated lifecycle</caption>
        <thead><tr><th>Workload / criticality</th><th>Status / action</th><th>Power</th><th>Remaining</th><th>Deadline UTC</th><th>Decision explanation</th></tr></thead>
        <tbody>{data.workloads.map((job) => { const d = decisions.get(job.job_id); return <tr key={job.job_id}>
          <td><a href={`#/jobs/${job.job_id}`}>{job.name}</a><div className="small muted">{job.criticality}</div></td>
          <td><Status value={job.status} /><div className="small">{job.last_power_action}</div><div className="small muted">{job.execution_status}</div></td>
          <td className="num">{job.estimated_power_kw} kW</td><td>{runtime(job.remaining_runtime_s)}</td>
          <td className="mono small">{job.request.deadline || 'Continuous service'}</td>
          <td className="ops-reason">{d?.reason}<div className="small muted">Deadline: {d?.deadline_feasible ? 'feasible under current assumptions' : 'INFEASIBLE'}
            {d?.deadline_slack_s != null && ` · slack ${runtime(Math.max(0, d.deadline_slack_s))}`}</div>
            {job.criticality === 'CHECKPOINTABLE' && <div className="small">Checkpoint/resume: SIMULATED; no AWS process was paused.</div>}
            {job.resumed_at && <div className="small">Resumed: {job.resumed_at}</div>}</td>
        </tr>; })}</tbody></table></div>
      <p className="small">Critical services preserved: {m?.critical_jobs_preserved} · deferred queue: {m?.workloads_deferred} · deadlines: {m?.deadlines_feasible ? 'feasible' : 'INFEASIBLE — see decisions'}.</p>

  </>;
}
