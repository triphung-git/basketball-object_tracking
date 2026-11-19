/* Causal overlay playback and a single cancellable video-frame subscription. */
(function (root) {
  function boxesAt(frames, time) {
    let lo = 0, hi = frames.length - 1, index = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (frames[mid].time <= time) { index = mid; lo = mid + 1; }
      else hi = mid - 1;
    }
    if (index < 0 || time - frames[index].time > .3) return [];
    const first = frames[index], next = frames[index + 1];
    const later = new Map((next?.boxes || []).filter(b => b.id).map(b => [b.id, b]));
    return first.boxes.filter(b => !b.sample_type || b.sample_type === "observed").map(item => {
      const following = item.id && later.get(item.id);
      // Only interpolate human tracks whose intervening source observations
      // prove continuity. Never reveal a future box or future identity.
      if (!following || !next || next.time <= first.time || next.time - first.time > .3
          || !Number.isFinite(following.continuity_start_s) || following.continuity_start_s > first.time
          || !item.segment_id || item.segment_id !== following.segment_id
          || ["role", "team_id", "player_id"].some(k => item[k] !== following[k])) return item;
      const alpha = (time - first.time) / (next.time - first.time);
      return {...item, box: item.box.map((v, i) => Number(v) + alpha * (Number(following.box[i]) - Number(v)))};
    });
  }

  function frameSync(video, render, animation = globalThis) {
    let id = null, kind = null;
    function stop() {
      if (id !== null) {
        if (kind === "video") video.cancelVideoFrameCallback(id);
        else animation.cancelAnimationFrame(id);
      }
      id = null;
    }
    function tick(now, metadata) {
      id = null;
      if (video.paused || video.ended) return;
      render(metadata?.mediaTime ?? video.currentTime);
      start();
    }
    function start() {
      if (id !== null || video.paused || video.ended) return;
      kind = typeof video.requestVideoFrameCallback === "function" ? "video" : "animation";
      id = kind === "video" ? video.requestVideoFrameCallback(tick) : animation.requestAnimationFrame(tick);
    }
    return {start, stop};
  }
  root.OverlayPlayback = {boxesAt, frameSync};
  if (typeof module !== "undefined") module.exports = root.OverlayPlayback;
})(globalThis);
