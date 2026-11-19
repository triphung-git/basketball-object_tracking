/* Display interpolation only. Occupancy always comes from backend intervals. */
(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.SpatialPlayback = api;
})(typeof globalThis === 'object' ? globalThis : this, function() {
  function frameAt(frames, t, exclusions = []) {
    if (!frames?.length || !Number.isFinite(t) || exclusions.some(e => e.start_s <= t && t < e.end_s)) return null;
    let lo = 0, hi = frames.length - 1, index = -1;
    while (lo <= hi) { const mid = (lo+hi)>>1; if (frames[mid].time <= t+.000001) { index=mid;lo=mid+1; } else hi=mid-1; }
    if (index < 0 || t-frames[index].time > .3) return null;
    const before = frames[index], after = frames[index+1];
    if (!after || after.time-before.time > .3 || t <= before.time || exclusions.some(e => e.start_s < after.time && e.end_s > before.time)) return before;
    const next = new Map(after.players.map(p => [p.id, p]));
    const fraction = (t-before.time)/(after.time-before.time);
    return {...before, players: before.players.map(p => {
      const q = next.get(p.id);
      if (!p.xy || !q?.xy || !Number.isFinite(q.continuity_start_s) || q.continuity_start_s > before.time+.000001 ||
          p.segment !== q.segment || p.player_id !== q.player_id || p.team_id !== q.team_id || p.role !== q.role ||
          JSON.stringify(p.source_scope) !== JSON.stringify(q.source_scope)) return p;
      return {...p, xy:p.xy.map((value, i) => value+(q.xy[i]-value)*fraction), display_interpolated:true};
    })};
  }
  return {frameAt};
});
