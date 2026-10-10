"""Deterministic facility constraint gate shared by telemetry and cloud launch.

No region-wide diesel assumptions; this policy never relocates a workload.
Runtime/overhead are seconds; power is kW. No known restoration time is assumed.
"""
from datetime import datetime, timezone

CLASSES = {"CRITICAL", "DEADLINE", "CHECKPOINTABLE", "INTERRUPTIBLE"}
TERMINAL = {"done", "failed", "infeasible"}


def utc(value):
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must include UTC offset")
    return dt.astimezone(timezone.utc)


def decide(facility, workloads, now):
    """Apply hard constraints before power/environment preferences, in stable order."""
    generator = facility["power_state"] == "GENERATOR"
    recovering = facility["power_state"] == "GRID_RECOVERY"
    ready = not recovering or (now - utc(facility["state_changed_at"])).total_seconds() >= facility["recovery_hysteresis_s"]
    horizon = facility.get("reevaluation_s", 1800)
    capacity = facility["generator_capacity_kw"] if generator else facility["grid_capacity_kw"]
    available = max(0, capacity - facility.get("base_load_kw", 0))
    by_id = {j["job_id"]: j for j in workloads}
    ordered = sorted(workloads, key=lambda j: (j.get("criticality") != "CRITICAL",
                     j.get("request", {}).get("deadline") or "9999", j["job_id"]))
    decisions = []
    for j in ordered:
        power = j["estimated_power_kw"]
        remaining = j.get("remaining_runtime_s")
        overhead = j.get("checkpoint_overhead_s", 0) + j.get("resume_overhead_s", 0)
        deadline = j.get("request", {}).get("deadline")
        slack = None if not deadline or remaining is None else (utc(deadline) - now).total_seconds() - remaining - overhead
        simulated = j.get("execution_mode") == "SIMULATED_FACILITY"
        running = j["status"] == "running"
        can_pause = simulated and (j["criticality"] == "INTERRUPTIBLE" or
                                   (j["criticality"] == "CHECKPOINTABLE" and j.get("checkpoint_supported")))
        action, reason, feasible = "CONTINUE", "Grid operation; original placement and residency retained.", True
        if j["status"] in TERMINAL:
            action, reason = "NO_ACTION", "Workload is terminal."
            feasible = j["status"] == "done"
            completed = j.get("completed_at") or j.get("updated_at")
            if feasible and deadline:
                feasible = bool(completed and utc(completed) <= utc(deadline))
                if not feasible:
                    reason = "Workload completed without confirmation of meeting its deadline."
            slack = None
        elif j.get("recovery_plan_error"):
            action, reason, feasible = "INFEASIBLE", "Recovery placement infeasible: " + j["recovery_plan_error"], False
        elif j.get("request", {}).get("max_delay_h") is not None and (now - utc(j["submitted_at"])).total_seconds() > j["request"]["max_delay_h"] * 3600 and j["status"] in {"placed", "waiting", "deferred"}:
            action, reason, feasible = "INFEASIBLE", "Mandatory maximum start delay has elapsed.", False
        elif slack is not None and slack < 0:
            action, reason, feasible = "INFEASIBLE", "Remaining runtime plus overhead exceeds deadline.", False
        elif any(by_id.get(d, {}).get("status") != "done" for d in j.get("dependencies", [])):
            action, reason = "DEFER", "Mandatory dependencies have not completed."
            if j["criticality"] == "CRITICAL" or (slack is not None and slack <= horizon):
                action, reason, feasible = "INFEASIBLE", "Dependency blocks mandatory execution; deadline cannot be guaranteed.", False
        elif facility.get("allowed_regions") and j.get("placement", {}).get("chosen", {}).get("region") not in facility["allowed_regions"] and not simulated:
            action, reason, feasible = "INFEASIBLE", "Selected placement is outside the facility's allowed compute regions.", False
        elif j["criticality"] == "CRITICAL":
            reason = "Critical service protected; environmental preferences cannot defer it."
        elif generator and slack is not None and slack <= horizon:
            action = "RESUME" if j["status"] == "deferred" else "CONTINUE"
            reason = "Deadline slack cannot support another decision horizon; execute now."
        elif running and not can_pause:
            reason = "Execution adapter cannot safely pause this running job; continue (no checkpoint claim)."
        elif recovering and not ready and (j["status"] == "deferred" or j.get("power_hold")) and (slack is None or slack > horizon):
            action, reason = "DEFER", "Waiting for stable-grid recovery hysteresis."
        elif generator and slack is not None and slack > horizon:
            action = "CHECKPOINT_AND_DEFER" if running and can_pause and j["criticality"] == "CHECKPOINTABLE" else "DEFER"
            reason = "Deadline slack permits one decision horizon of deferral, including checkpoint/resume overhead; restoration time is unknown."
        else:
            if j["status"] == "deferred":
                action = "RESUME"
            elif j.get("power_hold") and not generator:
                action = "REPLAN"
            reason = "Deadline boundary requires execution now." if generator else reason
        if action in {"CONTINUE", "RESUME", "REPLAN"}:
            if power > available:
                if j["criticality"] == "CRITICAL" or running or (slack is not None and slack <= horizon):
                    action, reason, feasible = "INFEASIBLE", "Facility capacity cannot support mandatory demand; running processes are not physically stopped.", False
                else:
                    action, reason = "DEFER", "Capacity queue; reevaluate after running work completes."
            else:
                available -= power
        decisions.append({"job_id": j["job_id"], "action": action, "reason": reason,
                          "deadline_feasible": feasible, "deadline_slack_s": slack,
                          "estimated_power_kw": power, "execution_status": "SIMULATED" if simulated else "ADVISORY",
                          "assumptions": ["MODELED IT power", "No known grid restoration time", "No relocation", f"Decision horizon {horizon} seconds"]})
    return decisions
