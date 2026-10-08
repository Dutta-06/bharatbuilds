import React, { useState } from "react";
import { api } from "../api.js";
import { ErrorBox, PageHead } from "./common.jsx";

// Cognito USER_PASSWORD_AUTH via the public API (no SDK). Needs VITE_COGNITO_REGION and
// VITE_COGNITO_CLIENT_ID (stack outputs). Untested until a user pool exists: see HUMAN-TODO.
const REGION = import.meta.env.VITE_COGNITO_REGION || "ap-south-1";
const CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID;

async function signIn(email, password) {
  const resp = await fetch(`https://cognito-idp.${REGION}.amazonaws.com/`, {
    method: "POST",
    headers: { "content-type": "application/x-amz-json-1.1", "x-amz-target": "AWSCognitoIdentityProviderService.InitiateAuth" },
    body: JSON.stringify({ AuthFlow: "USER_PASSWORD_AUTH", ClientId: CLIENT_ID, AuthParameters: { USERNAME: email, PASSWORD: password } }),
  });
  const body = await resp.json();
  if (!resp.ok || !body.AuthenticationResult) throw new Error(body.message || "Sign-in failed");
  return body.AuthenticationResult.IdToken;
}

async function policyCall(method, team, token, payload) {
  const resp = await fetch(`${api.base}/policies/${encodeURIComponent(team)}`, {
    method, headers: { "content-type": "application/json", authorization: token },
    body: payload ? JSON.stringify(payload) : undefined,
  });
  const body = await resp.json().catch(() => ({}));
  if (resp.status === 404) return null;
  if (!resp.ok) throw new Error(body.error || body.message || `API error ${resp.status}`);
  return body;
}

export default function Policies() {
  const [token, setToken] = useState(null);
  const [cred, setCred] = useState({ email: "", password: "" });
  const [team, setTeam] = useState("ml");
  const [policy, setPolicy] = useState(null);
  const [water, setWater] = useState(50);
  const [msg, setMsg] = useState(null);
  const [error, setError] = useState(null);

  if (!CLIENT_ID) {
    return (<><PageHead eyebrow="Platform leads" title="Team policies" />
      <div className="banner warn">Sign-in is not configured. Set <code>VITE_COGNITO_CLIENT_ID</code> (stack output <code>UserPoolClientId</code>) and rebuild.</div></>);
  }
  const run = (f) => async (e) => { e?.preventDefault(); setError(null); setMsg(null); try { await f(); } catch (err) { setError(err); } };
  return (
    <>
      <PageHead eyebrow="Platform leads" title="Team policies">
        Set each team's water and carbon weights. A job that names its team is placed under that team's policy, whatever the submitter chose.
      </PageHead>
      <ErrorBox error={error} />
      <div style={{ maxWidth: 460 }}>
      {!token ? (
        <form className="panel stack" onSubmit={run(async () => setToken(await signIn(cred.email, cred.password)))}>
          <div className="section-title" style={{ margin: 0 }}>Sign in</div>
          <div className="field"><label className="lbl" htmlFor="email">Email</label>
            <input id="email" type="text" autoComplete="username" value={cred.email} onChange={(e) => setCred({ ...cred, email: e.target.value })} /></div>
          <div className="field"><label className="lbl" htmlFor="pw">Password</label>
            <input id="pw" type="password" autoComplete="current-password" value={cred.password} onChange={(e) => setCred({ ...cred, password: e.target.value })} /></div>
          <div><button className="primary">Sign in</button></div>
        </form>
      ) : (
        <form className="panel stack" onSubmit={run(async () => {
          const saved = await policyCall("PUT", team, token, { ...(policy || {}), weights: { water: water / 100, carbon: 1 - water / 100 } });
          setPolicy(saved); setMsg(`Saved. The next job for team ${team} uses it.`);
        })}>
          <div className="field"><label className="lbl" htmlFor="team">Team</label>
            <div className="row"><input id="team" type="text" value={team} onChange={(e) => setTeam(e.target.value)} style={{ flex: 1, minWidth: 0 }} />
              <button type="button" className="btn" onClick={run(async () => {
                const p = await policyCall("GET", team, token); setPolicy(p);
                if (p) setWater(Math.round(p.weights.water * 100));
                setMsg(p ? `Loaded the policy for ${team}.` : `No policy for ${team} yet. Saving creates one.`);
              })}>Load</button></div></div>
          <div className="field"><label className="lbl" htmlFor="w">Optimise for</label>
            <input id="w" type="range" min="0" max="100" step="10" value={water} onChange={(e) => setWater(Number(e.target.value))} aria-valuetext={`${water}% water, ${100 - water}% carbon`} />
            <div className="row small num" style={{ justifyContent: "space-between" }}><span>carbon {100 - water}%</span><span>water {water}%</span></div></div>
          <div><button className="primary">Save policy</button></div>
          {msg && <p className="small" role="status">{msg}</p>}
        </form>
      )}
      </div>
    </>
  );
}
