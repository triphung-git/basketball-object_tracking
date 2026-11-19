/* Source-frame court calibration editor. Drafts are saved only through MatchUI. */
(() => {
  let config = null, draft = null, editing = -1, roiMode = false, preview = [], revision = 0;
  let hooks = null, pending = false;
  const image = document.createElement('canvas');
  const surface = document.getElementById('calibrationImage');
  const el = id => document.getElementById(id);
  const status = text => { el('calibrationStatus').textContent = text; };
  const landmarks = [
    ['Góc lane trái ở baseline', -2.45, 0], ['Góc lane phải ở baseline', 2.45, 0],
    ['Góc lane trái ở vạch ném phạt', -2.45, 5.8], ['Góc lane phải ở vạch ném phạt', 2.45, 5.8],
    ['Giữa vạch ném phạt', 0, 5.8], ['Góc sân trái ở baseline', -7.5, 0],
    ['Góc sân phải ở baseline', 7.5, 0], ['Đỉnh cung xa', 0, 8.325], ['Tọa độ tự nhập', null, null],
  ];
  landmarks.forEach((p, i) => el('calLandmark').add(new Option(p[0], String(i))));
  el('calLandmark').onchange = () => {
    const [, x, y] = landmarks[Number(el('calLandmark').value)];
    if (x !== null) { el('calX').value = x; el('calY').value = y; }
  };
  function clone(value) { return JSON.parse(JSON.stringify(value)); }
  function clearPreview() { preview = []; revision++; }
  function render() {
    el('previewCalibration').disabled = el('applyCalibration').disabled = pending || !image.dataset.captured;
    const ctx = surface.getContext('2d');
    ctx.clearRect(0, 0, surface.width, surface.height);
    ctx.fillStyle = '#172c40'; ctx.fillRect(0, 0, surface.width, surface.height);
    if (image.width && image.height && image.dataset.captured) ctx.drawImage(image, 0, 0, surface.width, surface.height);
    else { ctx.fillStyle = 'white'; ctx.font = '20px Segoe UI'; ctx.fillText('Dừng video rồi lấy khung hình hiệu chuẩn', 24, 45); }
    if (!draft || !config) return;
    const sx = surface.width / config.width, sy = surface.height / config.height;
    ctx.save(); ctx.scale(sx, sy);
    ctx.strokeStyle = '#24d6df'; ctx.lineWidth = 2 / sx;
    for (const line of preview) {
      ctx.beginPath(); ctx.moveTo(...line[0]); ctx.lineTo(...line[1]); ctx.stroke();
    }
    if (draft.roi_image.length) {
      ctx.strokeStyle = '#48e59f'; ctx.beginPath(); draft.roi_image.forEach((p, i) => i ? ctx.lineTo(...p) : ctx.moveTo(...p));
      if (!roiMode) ctx.closePath(); ctx.stroke();
    }
    draft.points.forEach((p, i) => {
      ctx.fillStyle = p.usage === 'check' ? '#ffe278' : '#ff754b';
      ctx.beginPath(); ctx.arc(...p.image, 5 / sx, 0, Math.PI * 2); ctx.fill();
      ctx.font = `${15 / sx}px Segoe UI`; ctx.fillText(String(i + 1), p.image[0] + 8 / sx, p.image[1] - 5 / sy);
    });
    ctx.restore();
    el('calAnchor').textContent = `Khung tham chiếu: ${draft.anchor_s.toFixed(3)} s`;
    el('calibrationPoints').replaceChildren();
    draft.points.forEach((p, i) => {
      const row = document.createElement('p'), text = document.createElement('span'), remove = document.createElement('button');
      text.textContent = `${i + 1}. (${p.court.join('; ')}) m · ${p.usage === 'check' ? 'kiểm tra' : 'khớp'}`;
      remove.type = 'button'; remove.textContent = 'Bỏ'; remove.setAttribute('aria-label', `Bỏ mốc ${i + 1}`);
      remove.onclick = () => { draft.points.splice(i, 1); delete draft.keyframes; clearPreview(); render(); };
      row.append(text, remove); el('calibrationPoints').append(row);
    });
  }
  function lists() {
    if (!config) return;
    el('calibrationSegments').replaceChildren();
    config.segments.forEach((s, i) => {
      const edit = document.createElement('button'), remove = document.createElement('button');
      edit.type = remove.type = 'button';
      edit.textContent = `${s.start_s.toFixed(2)}–${s.end_s.toFixed(2)} s · ${s.points.length} mốc${s.enabled === false ? ' · tắt' : ''}`;
      edit.onclick = () => {
        editing = i; draft = clone({...s, anchor_s: s.anchor_s ?? s.start_s, roi_image: s.roi_image || []});
        el('calStart').value = s.start_s; el('calEnd').value = s.end_s; clearPreview();
        hooks.video.pause(); hooks.video.currentTime = draft.anchor_s;
        image.dataset.captured = ''; render(); status('Đang lấy đúng khung tham chiếu…');
        if (Math.abs(hooks.video.currentTime - draft.anchor_s) < .025 && !hooks.video.seeking) capture(false);
      };
      remove.textContent = 'Bỏ khoảng'; remove.onclick = () => { config.segments.splice(i, 1); editing = -1; draft = null; clearPreview(); lists(); render(); hooks.changed(); };
      el('calibrationSegments').append(edit, remove);
    });
    el('exclusionList').replaceChildren();
    config.exclusions.forEach((e, i) => {
      const button = document.createElement('button'); button.type = 'button';
      button.textContent = `${e.start_s.toFixed(2)}–${e.end_s.toFixed(2)} s ×`;
      button.onclick = () => { config.exclusions.splice(i, 1); lists(); hooks.changed(); };
      el('exclusionList').append(button);
    });
  }
  function newDraft() {
    if (!config) return;
    editing = -1; roiMode = false; clearPreview();
    image.dataset.captured = '';
    const t = Math.min(hooks.duration(), Math.max(0, hooks.video.currentTime));
    draft = {start_s: t, end_s: Math.min(hooks.duration(), t + 5), anchor_s: t, points: [], roi_image: [], enabled: true};
    el('calStart').value = draft.start_s.toFixed(3); el('calEnd').value = draft.end_s.toFixed(3);
    render();
    capture(false);
  }
  function capture(clearPoints = true) {
    if (!config || !draft || hooks.video.readyState < 2 || hooks.video.seeking) { status('Chờ video tải xong khung hình rồi thử lại.'); return; }
    hooks.video.pause();
    const t = hooks.video.currentTime;
    if (clearPoints && Math.abs(draft.anchor_s - t) > .025) { draft.points = []; draft.roi_image = []; delete draft.keyframes; clearPreview(); }
    draft.anchor_s = t;
    image.width = config.width; image.height = config.height;
    image.getContext('2d').drawImage(hooks.video, 0, 0, image.width, image.height);
    image.dataset.captured = '1';
    surface.width = 960; surface.height = Math.round(960 * config.height / config.width);
    render(); status('Chọn mốc sân rồi bấm vị trí trên ảnh. Cần ít nhất 4 mốc khớp không thẳng hàng.');
  }
  function draftConfig() {
    if (!draft || !image.dataset.captured) throw new Error('Lấy khung hình trước khi kiểm tra.');
    const candidate = clone(hooks.collect());
    draft.start_s = Number(el('calStart').value); draft.end_s = Number(el('calEnd').value);
    if (roiMode) throw new Error('Đóng vùng mặt sân trước khi áp dụng.');
    if (editing >= 0) candidate.segments[editing] = clone(draft); else candidate.segments.push(clone(draft));
    return candidate;
  }
  async function validate(apply) {
    if (pending || !hooks) return;
    const token = revision;
    pending = true; el('previewCalibration').disabled = el('applyCalibration').disabled = true;
    try {
      const request = draftConfig(); status('Đang kiểm tra mốc sân…');
      const response = await hooks.preview(request);
      if (token !== revision) return;
      const segment = response.segments.find(s => Math.abs(s.start_s - draft.start_s) < 1e-6);
      preview = segment?.lines || []; render();
      const checks = segment?.check_residuals_px || [], fit = segment?.fit_residuals_px || [];
      status(`Sai số khớp lớn nhất ${Math.max(0, ...fit).toFixed(2)} px. ${checks.length ? `Kiểm tra độc lập ${Math.max(...checks).toFixed(2)} px.` : 'Chưa có mốc kiểm tra độc lập.'} Đối chiếu lưới cyan với mặt sân.`);
      if (apply) {
        config.segments = response.config.segments; editing = config.segments.findIndex(s => Math.abs(s.start_s-draft.start_s)<1e-6);
        draft = clone(config.segments[editing]); lists(); hooks.changed();
        status('Đã áp dụng vào bản nháp. Bấm Lưu thiết lập hoặc Cập nhật bản đồ sân.');
      }
    } catch (e) { if (token === revision) status(e.message); }
    finally { pending = false; el('previewCalibration').disabled = el('applyCalibration').disabled = !image.dataset.captured; }
  }
  surface.addEventListener('click', e => {
    if (!draft || !config || !image.dataset.captured || pending) return;
    const b = surface.getBoundingClientRect(), point = [(e.clientX-b.left)/b.width*config.width, (e.clientY-b.top)/b.height*config.height].map(v => Math.round(v * 100) / 100);
    clearPreview();
    if (roiMode) { draft.roi_image.push(point); render(); return; }
    delete draft.keyframes;
    const x = Number(el('calX').value), y = Number(el('calY').value), ymax = config.format === '5x5' ? 28 : 11;
    if (!Number.isFinite(x) || !Number.isFinite(y) || x < -7.5 || x > 7.5 || y < 0 || y > ymax) { status('Tọa độ mốc nằm ngoài sân.'); return; }
    draft.points.push({image: point, court: [x, y], usage: el('calUsage').value}); render();
  });
  el('newCalibration').onclick = newDraft;
  el('captureCalibration').onclick = () => draft ? capture(true) : newDraft();
  el('previewCalibration').onclick = () => validate(false);
  el('applyCalibration').onclick = () => validate(true);
  el('undoCalibrationPoint').onclick = () => { if (draft && !pending) { draft.points.pop(); delete draft.keyframes; clearPreview(); render(); } };
  el('startCourtRoi').onclick = () => { if (draft && !pending) { draft.roi_image = []; roiMode = true; clearPreview(); render(); status('Bấm ít nhất 3 đỉnh quanh vùng mặt sân, sau đó bấm Đóng vùng.'); } };
  el('finishCourtRoi').onclick = () => { if (!draft || draft.roi_image.length < 3) { status('ROI cần ít nhất 3 đỉnh.'); return; } roiMode = false; render(); };
  el('clearCourtRoi').onclick = () => { if (draft && !pending) { draft.roi_image = []; roiMode = false; clearPreview(); render(); } };
  el('addExclusion').onclick = () => {
    if (!config) return;
    const start_s = Number(el('excludeStart').value), end_s = Number(el('excludeEnd').value);
    if (!Number.isFinite(start_s) || !Number.isFinite(end_s) || start_s < 0 || end_s <= start_s || end_s > hooks.duration()) { status('Khoảng loại trừ phải nằm trong video và có độ dài dương.'); return; }
    config.exclusions.push({start_s, end_s}); lists(); hooks.changed();
  };
  for (const id of ['calStart', 'calEnd']) el(id).addEventListener('input', () => { clearPreview(); render(); });
  window.CalibrationEditor = {
    load(value, callbacks) {
      revision++; config = value; hooks = callbacks; draft = null; editing = -1; preview = []; roiMode = false; image.dataset.captured = ''; lists(); render();
      status(value.segments.length ? 'Chọn khoảng sân để kiểm tra hoặc thêm khoảng mới.' : 'Chọn một cảnh toàn sân và bấm Thêm khoảng sân.');
    },
    reset() { revision++; config = draft = null; preview = []; image.dataset.captured = ''; render(); },
  };
  document.getElementById('gameVideo').addEventListener('seeked', () => {
    if (draft && !image.dataset.captured && Math.abs(hooks.video.currentTime-draft.anchor_s) < .05) capture(false);
  });
})();
