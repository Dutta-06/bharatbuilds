export function runtime(seconds) {
  if (seconds == null) return 'Continuous';
  return `${Math.round(seconds / 60)} min`;
}

export function powerLabel(state) {
  return ({ GRID: 'Grid', GENERATOR: 'Generator backup', BATTERY_TRANSITION: 'Battery transition', GRID_RECOVERY: 'Grid recovery' })[state] || 'Unknown';
}

export function canOperate(token, now = Date.now()) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    const groups = payload['cognito:groups'];
    return payload.exp * 1000 > now && (Array.isArray(groups) ? groups.includes('platform-leads') :
      String(groups || '').replace(/[\[\]"']/g, '').split(/[ ,]+/).includes('platform-leads'));
  } catch { return false; }
}
