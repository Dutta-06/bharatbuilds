import React, { useState } from "react";
import { api } from "../api.js";
import { ErrorBox } from "./common.jsx";

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
    return (<><h1>Team policies</h1><div className="card">Sign-in is not configured. Set
      <code> VITE_COGNITO_CLIENT_ID</code> (stack output <code>UserPoolClientId</code>) and rebuild.</div></>);
  }
  const run = (f) => async (e) => { e?.preventDefault(); setError(null); setMsg(null); try { await f(); } catch (err) { setError(err); } };
  return (
    <>
      <h1>Team policies</h1>
      <p className="lede">Platform leads set each team's water/carbon weights and allowed regions. Jobs that name the
        team are placed under its policy.</p>
      <ErrorBox error={error} />
      {!token ? (
        <form className="card" onSubmit={run(async () => setToken(await signIn(cred.email, cred.password)))}>
          <label>Email<input type="text" value={cred.email} onChange={(e) => setCred({ ...cred, email: e.target.value })} /></label>
          <label>Password<input type="password" value={cred.password} onChange={(e) => setCred({ ...cred, password: e.target.value })}
            style={{ display: "block", width: "100%", marginTop: 4, padding: 8 }} /></label>
          <button className="primary">Sign in</button>
        </form>
      ) : (
        <form className="card" onSubmit={run(async () => {
          const saved = await policyCall("PUT", team, token, { ...(policy || {}), weights: { water: water / 100, carbon: 1 - water / 100 } });
          setPolicy(saved); setMsg(`Saved. The next job for team ${team} uses it.`);
        })}>
          <label>Team<input type="text" value={team} onChange={(e) => setTeam(e.target.value)} /></label>
          <p><button type="button" className="primary" onClick={run(async () => {
            const p = await policyCall("GET", team, token); setPolicy(p);
            if (p) setWater(Math.round(p.weights.water * 100));
            setMsg(p ? null : `No policy for ${team} yet.`);
          })}>Load</button></p>
          <label>Water vs carbon: <strong>{water}% / {100 - water}%</strong>
            <input type="range" min="0" max="100" step="10" value={water} onChange={(e) => setWater(Number(e.target.value))} /></label>
          <button className="primary">Save policy</button>
          {msg && <p className="small">{msg}</p>}
        </form>
      )}
    </>
  );
}
