/* Match configuration, reviewed track identities and source-time court playback. */
(() => {
  let config = null, result = null, duration = 0, loadedJob = null;
  let picking = false, pending = false, selectedTrack = "";
  let requestSerial = 0, activeRebuild = false;
  let trackCatalog = [];
  let savedRevision = null;
  const hex = rgb => "#" + rgb.map(v => Math.round(v).toString(16).padStart(2, "0")).join("");
  const rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const say = text => { $("matchStatus").textContent = text; };
  const postJson = (path, data) => api(path, {method: "POST", headers: {"X-Demo-Request": "1", "Content-Type": "application/json"}, body: JSON.stringify(data)}, loadedJob);
  const teamName = id => id === config?.roster.team_a_id ? config.roster.team_a_name : id === config?.roster.team_b_id ? config.roster.team_b_name : "Chưa rõ đội";
  const person = id => config?.roster.players.find(p => p.player_id === id);
  const color = id => id === config?.roster.team_a_id ? hex(config.roster.team_a_color_rgb) : id === config?.roster.team_b_id ? hex(config.roster.team_b_color_rgb) : "#64748b";
  const assignmentFor = (track, t = video.currentTime) =>
    config?.assignments.find(a => a.track_id === track && a.start_s <= t && t < a.end_s);
  const reviewedLabel = (track, t, box) => {
    const mapping = assignmentFor(track, t);
    if (mapping?.role !== "player" || !mapping.player_id || mapping.player_id !== box.player_id) return null;
    const p = person(mapping.player_id);
    if (!p?.is_active || p.team_id !== box.team_id) return null;
    return `${teamName(p.team_id)} · #${p.jersey_number} ${p.name}`;
  };
  const shortLabel = (track, t = video.currentTime, snapshot = null) => {
    if (!config) return null;
    const mapping = assignmentFor(track, t);
    if (mapping) {
      if (mapping.role === "non_player") return "Ngoài sân";
      if (mapping.role === "referee") return "Trọng tài";
      const p = person(mapping.player_id);
      return p ? `#${p.jersey_number} ${p.name}` : teamName(mapping.team_id);
    }
    const frame = frameAt(t);
    const item = frame?.players.find(p => p.id === track) || snapshot;
    if (item?.role === "referee") return "Trọng tài";
    if (item?.role === "non_player") return "Ngoài sân";
    const p = person(item?.player_id);
    if (p) return `#${p.jersey_number} ${p.name}`;
    const tid = item?.team_id || result?.color_teams?.[track];
    if (tid) return teamName(tid);
    return null;
  };

  function reset() {
    requestSerial++;
    config = result = null;
    savedRevision = null;
    trackCatalog = [];
    loadedJob = null;
    selectedTrack = "";
    activeRebuild = false;
    picking = false;
    window.CalibrationEditor?.reset();
    canvas.style.pointerEvents = "none";
    $("pickTrack").textContent = "Chọn người trên video";
    $("selectedTrackNote").textContent = "Chưa chọn mã theo dõi.";
    $("addAssignment").disabled = true;
    if ($('playerMappingNote')) $('playerMappingNote').textContent='';
    for (const id of ["matchSetup", "spatialPanel"]) $(id).hidden = true;
    say("");
  }

  function fillForm() {
    const r = config.roster;
    $("matchFormat").value = config.format;
    $("teamAName").value = r.team_a_name;
    $("teamBName").value = r.team_b_name;
    $("teamAColor").value = hex(r.team_a_color_rgb);
    $("teamBColor").value = hex(r.team_b_color_rgb);
    for (const [field, id] of [["rosterA", r.team_a_id], ["rosterB", r.team_b_id]]) {
      $(field).value = r.players.filter(p => p.team_id === id).map(p => `${p.jersey_number}, ${p.name}`).join("\n");
    }
    $("classifyTeams").checked = config.classify_teams;
    $("heatEnd").value = duration;
    renderLists();
    playerOptions();
    loadCalibrationEditor();
  }

  function loadCalibrationEditor() {
    window.CalibrationEditor?.load(config, {video, duration:()=>duration, collect:collectForm,
      preview:data=>postJson('/api/calibration/preview', data),
      changed:()=>{result=null;draw();drawHeatmap();say('Có thay đổi chưa lưu. Lưu thiết lập và cập nhật bản đồ sân.');}});
  }

  function collectForm() {
    const r = config.roster;
    const previous = r.players;
    const roster = [];
    for (const [field, team] of [["rosterA", r.team_a_id], ["rosterB", r.team_b_id]]) {
      for (const line of $(field).value.split("\n").map(s => s.trim()).filter(Boolean)) {
        const match = line.match(/^([^,;]+)[,;]\s*(.*)$/);
        if (!match || !match[1].trim() || !match[2].trim()) throw new Error("Nhập cầu thủ theo dạng: số áo, tên; mỗi cầu thủ một dòng.");
        const jersey = match[1].trim(), name = match[2].trim();
        const old = previous.find(p => p.team_id === team && p.jersey_number === jersey);
        roster.push({player_id: old?.player_id || `${team}_jersey_${jersey}`, team_id: team, jersey_number: jersey, name});
      }
    }
    r.players = roster;
    r.team_a_name = $("teamAName").value.trim() || "Đội A";
    r.team_b_name = $("teamBName").value.trim() || "Đội B";
    r.team_a_color_rgb = rgb($("teamAColor").value);
    r.team_b_color_rgb = rgb($("teamBColor").value);
    r.provenance_status = "user_configured";
    config.format = $("matchFormat").value;
    config.classify_teams = $("classifyTeams").checked;
    return config;
  }

  function playerOptions() {
    const value = $("assignmentPlayer").value;
    $("assignmentPlayer").replaceChildren();
    for (const [id, label] of [["", "Chọn đội / cầu thủ"], ["referee", "Trọng tài"], ["non_player", "Ngoài sân / không phải cầu thủ"], ["team:"+config.roster.team_a_id, config.roster.team_a_name], ["team:"+config.roster.team_b_id, config.roster.team_b_name], ...config.roster.players.map(p => ["player:"+p.player_id, `${teamName(p.team_id)} · #${p.jersey_number} ${p.name}`])]) {
      $("assignmentPlayer").add(new Option(label, id));
    }
    $("assignmentPlayer").value = value;
    updateMappingNote();
  }

  function updateMappingNote() {
    if (!config) return;
    let note=$('playerMappingNote');
    if (!note) {
      note=document.createElement('p');note.id='playerMappingNote';note.className='match-note';
      note.setAttribute('role','status');note.setAttribute('aria-live','polite');
      $('assignmentList').before(note);
    }
    const players=new Set(config.roster.players.map(p=>p.player_id));
    const mapped=config.assignments.filter(a=>a.player_id&&players.has(a.player_id));
    const orphaned=config.assignments.some(a=>a.player_id&&!players.has(a.player_id));
    if(orphaned) {
      note.textContent='Có gán nhãn tới cầu thủ đã bị xóa hoặc đổi số áo. Chọn lại cầu thủ cho các bbox đó trước khi lưu.';
    } else if(!players.size) {
      note.textContent='Đội được nhận từ màu áo. Nhập đội hình để hệ thống đối chiếu số áo với tên cầu thủ; có thể gán hoặc sửa danh tính khi cần.';
    } else if(!mapped.length) {
      const identity=result?.identity;
      const status=activeRebuild ? 'Đang cập nhật nhận diện số áo.' : identity?.status==='unavailable' ? 'Chưa có model OCR cục bộ để xác minh tên.' : identity?.named_players ? `Đã xác minh ${identity.named_players}/${players.size} cầu thủ bằng số áo.` : 'Chưa có tên được xác minh từ số áo.';
      note.textContent=`Đã lưu ${players.size} cầu thủ. ${status} Người chưa đủ bằng chứng tiếp tục hiện tên đội và mã theo dõi. Có thể chọn bbox để bổ sung danh tính.`;
    } else {
      note.textContent=`Đã gán ${new Set(mapped.map(a=>a.player_id)).size}/${players.size} cầu thủ vào ${new Set(mapped.map(a=>a.track_id)).size} mã theo dõi. Nhãn chỉ áp dụng trong khoảng thời gian được gán; các bbox khác giữ tên đội hoặc mã theo dõi.`;
    }
  }

  function renderLists() {
    for (const [field, list, label] of [
      ["assignmentList", config.assignments, s => {
        const track = trackCatalog.find(t => t.id === s.track_id);
        const coversTrack = track && s.start_s <= track.start_s && s.end_s >= Math.min(duration, track.end_s + .001);
        const scope = coversTrack ? "toàn mã" : `${time(s.start_s)}–${time(s.end_s)}`;
        const roleLabel = s.role === "non_player" ? "Ngoài sân" : s.role === "referee" ? "Trọng tài" : person(s.player_id)?.name || teamName(s.team_id);
        return `${trackLabels.has(s.track_id) ? "Mã "+trackLabels.get(s.track_id) : s.track_id} → ${roleLabel} · ${scope}`;
      }],
    ]) {
      $(field).replaceChildren();
      list.forEach((s, i) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label(s) + " ×";
        button.title = "Bỏ gán này";
        button.onclick = () => { list.splice(i, 1); result=null; renderLists(); draw(); drawHeatmap(); drawOverlay(); say("Có thay đổi chưa lưu."); };
        $(field).append(button);
      });
    }
    updateMappingNote();
  }

  async function load(id, token) {
    if (!id) {
      reset();
      try {
        const startup=await api('/api/startup',{},null);
        if (!startup.has_spatial || token!==generation || jobId) return;
        const data=await api('/api/match',{},null);
        config=data.config;duration=data.duration_s;
        fillForm();$('spatialPanel').hidden=false;
        await fetchResult(null,requestSerial);
      } catch(e) { say(e.message); }
      return;
    }
    const serial = ++requestSerial;
    try {
      const data = await api("/api/match", {}, id);
      if (serial !== requestSerial || token !== generation || id !== jobId) return;
      loadedJob = id; config = data.config; duration = data.duration_s; result = null;savedRevision=data.revision;
      fillForm();
      drawOverlay();
      $("matchSetup").hidden = false;
      $("spatialPanel").hidden = false;
      $("rebuildMatch").disabled = jobStatus !== "completed";
      $("saveMatch").disabled = !["ready", "completed"].includes(jobStatus);
      draw();
      if (data.spatial.status === "completed") await fetchResult(id, serial);
      else if (data.spatial.status === "running") { activeRebuild = true; say("Đang dựng bản đồ từ dữ liệu đã lưu…"); }
      else if (jobStatus === "completed" && data.spatial.status === "unavailable") {
        await api("/api/rebuild", {method:"POST", headers:{"X-Demo-Request":"1"}}, id);
        if (serial !== requestSerial) return;
        activeRebuild = true; say("Đang dựng bản đồ sân từ tracking đã lưu…");
      } else say(data.spatial.status === "stale" ? "Thiết lập đã đổi. Đang chờ cập nhật kết quả." : "Lưu thông tin đội rồi bấm Phân tích để tự dựng sân.");
    } catch (e) { if (serial === requestSerial) say(e.message); }
  }

  async function fetchResult(id, serial) {
    const data = await api("/api/spatial", {}, id);
    if (serial !== requestSerial || id !== jobId) return;
    if (data.status !== "completed") { say("Kết quả cần được cập nhật."); return; }
    result = data;
    trackCatalog = data.tracks;
    $("assignmentTrack").replaceChildren(new Option("Chọn mã theo dõi", ""));
    for (const tr of data.tracks) {
      if (!trackLabels.has(tr.id)) trackLabels.set(tr.id, trackLabels.size+1);
      $("assignmentTrack").add(new Option(`Mã ${trackLabels.get(tr.id)} · ${time(tr.start_s)}–${time(tr.end_s)}`, tr.id));
    }
    const filter = $("spatialFilter");
    filter.replaceChildren(new Option("Cầu thủ đã xác nhận", "all"), new Option('Chưa rõ vai trò', 'unknown_role'), new Option('Cầu thủ chưa rõ đội', 'unknown_team'));
    for (const team of [config.roster.team_a_id, config.roster.team_b_id]) filter.add(new Option(teamName(team), "team:"+team));
    for (const p of config.roster.players) filter.add(new Option(`#${p.jersey_number} ${p.name}`, "player:"+p.player_id));
    for (const tr of data.tracks) if (data.heatmaps["track:"+tr.id]) filter.add(new Option(`Mã ${trackLabels.get(tr.id)}`, "track:"+tr.id));
    renderLists();
    drawHeatmap(); draw(); drawOverlay();
    const q = data.quality || {};
    const calibration = q.calibration_status === 'automatic_line_checked' ? 'Sân được dựng tự động và kiểm tra đường kẻ' : q.calibration_status === 'automatic_unavailable' ? 'Cảnh quay chưa đủ bằng chứng để dựng sân tự động' : q.calibration_status === 'checked_landmarks' ? 'Dữ liệu cũ có mốc kiểm tra' : q.calibration_status === 'uncalibrated' ? 'Chưa có geometry sân' : 'Dữ liệu hiệu chuẩn cũ';
    const coverage=q.geometry_total_frames ? ` Hỗ trợ geometry ở ${q.geometry_supported_frames}/${q.geometry_total_frames} khung hình.` : '';
    $('spatialQuality').textContent = `${calibration}.${coverage} Chiếu được ${((q.projection_fraction||0)*100).toFixed(1)}% quan sát người; đã ẩn ${q.duplicate_identity_markers||0} marker trùng danh tính. Sai số vị trí thực chưa có benchmark độc lập.`;
    $('rebuildMatch').hidden=true;
    updateMappingNote();
    say(q.calibration_status==='automatic_unavailable' ? 'Chưa đủ bằng chứng để dựng sân trong video này. Bbox và tracking vẫn có thể xem trên video.' : 'Bản đồ 2D và heatmap đã được dựng từ các vị trí sân hợp lệ.');
  }

  function frameAt(t) {
    return window.SpatialPlayback.frameAt(result?.frames, t, config?.exclusions || []);
  }
  const visible = p => {
    const f = $("spatialFilter").value;
    if (f === 'unknown_role') return p.role === 'unknown';
    if (p.role !== 'player') return false;
    if (f === 'unknown_team') return !p.team_id;
    return f === "all" || f === "team:"+p.team_id || f === "player:"+p.player_id || f === "track:"+p.id;
  };
  const uninterrupted = (start,end) => !config.exclusions.some(e=>e.start_s<end&&e.end_s>start);

  function court(surface) {
    const ctx = surface.getContext("2d"), w = surface.width, h = surface.height;
    const ymax = result?.bounds.y_max || (config?.format === "5x5" ? 28 : 11);
    const scale = Math.min((w-60)/15, (h-50)/ymax), ox = (w-15*scale)/2, oy = (h-ymax*scale)/2;
    const x = v => ox+(v+7.5)*scale, y = v => h-oy-v*scale;
    ctx.clearRect(0,0,w,h); ctx.fillStyle="#f4ede0"; ctx.fillRect(0,0,w,h);
    const lines = () => {
      ctx.strokeStyle="#a08d71"; ctx.lineWidth=1.6;
      if (result?.court_lines) {
        for (const line of result.court_lines) { ctx.beginPath(); line.forEach((p,i)=>i?ctx.lineTo(x(p[0]),y(p[1])):ctx.moveTo(x(p[0]),y(p[1])));ctx.stroke(); }
        return;
      }
      ctx.strokeRect(x(-7.5), y(ymax), 15*scale, ymax*scale);
      const end = flip => {
        const yy = v => y(flip ? ymax-v : v);
        ctx.strokeRect(x(-2.45), Math.min(yy(0),yy(5.8)), 4.9*scale, 5.8*scale);
        ctx.beginPath(); ctx.arc(x(0),yy(5.8),1.8*scale,0,Math.PI*2); ctx.stroke();
        const join = Math.sqrt(6.75**2-6.6**2), angle = Math.asin(join/6.75);
        ctx.beginPath(); ctx.moveTo(x(-6.6),yy(0)); ctx.lineTo(x(-6.6),yy(1.575+join)); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(x(6.6),yy(0)); ctx.lineTo(x(6.6),yy(1.575+join)); ctx.stroke();
        ctx.beginPath(); ctx.arc(x(0),yy(1.575),6.75*scale,flip ? angle : Math.PI+angle,flip ? Math.PI-angle : 2*Math.PI-angle); ctx.stroke();
        ctx.strokeStyle="#d17a25";ctx.beginPath();ctx.arc(x(0),yy(1.575),.23*scale,0,Math.PI*2);ctx.stroke();ctx.strokeStyle="#a08d71";
      };
      ctx.save();ctx.beginPath();ctx.rect(x(-7.5),y(ymax),15*scale,ymax*scale);ctx.clip();end(false);
      if(ymax>15) {end(true);ctx.beginPath();ctx.moveTo(x(-7.5),y(ymax/2));ctx.lineTo(x(7.5),y(ymax/2));ctx.stroke();ctx.beginPath();ctx.arc(x(0),y(ymax/2),1.8*scale,0,Math.PI*2);ctx.stroke();}
      ctx.restore();
    };
    lines();
    return {ctx,x,y,scale,lines,ymax,pixelRatio:w/Math.max(1,surface.clientWidth||w)};
  }

  function draw(mediaTime) {
    if (!config) return;
    const {ctx,x,y,pixelRatio} = court($("courtCanvas")), t=Number.isFinite(mediaTime)?mediaTime:video.currentTime, frame=frameAt(t);
    $("spatialTime").textContent=time(t);
    if (!frame?.players.some(p=>p.xy && visible(p))) {
      $("spatialNote").textContent = frame?.players.some(p=>p.xy && p.role==='unknown') ? 'Có vị trí chưa rõ vai trò. Chọn Chưa rõ vai trò để xem hoặc bổ sung danh tính.' : 'Khoảng này chưa có tọa độ được hỗ trợ. Hệ thống chỉ đưa cảnh có geometry hợp lệ vào bản đồ và heatmap.';
      return;
    }
    if ($("showTrails").checked) {
      const last = new Map();
      for (const f of result.frames) {
        if (f.time < t-3) continue;
        if (f.time > t) break;
        for (const p of f.players) {
          if (!p.xy || !visible(p)) { last.delete(p.id); continue; }
          const old=last.get(p.id);
          if(old && f.time-old.t<=.3 && p.continuity_start_s<=old.t+.000001 && uninterrupted(old.t,f.time) && p.segment===old.segment && p.player_id===old.player_id && p.role===old.role && p.team_id===old.team_id && JSON.stringify(p.source_scope)===old.scope && Math.hypot(p.xy[0]-old.xy[0],p.xy[1]-old.xy[1])<=12*(f.time-old.t)) {
            ctx.strokeStyle=color(p.team_id);ctx.globalAlpha=.4;ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x(old.xy[0]),y(old.xy[1]));ctx.lineTo(x(p.xy[0]),y(p.xy[1]));ctx.stroke();ctx.globalAlpha=1;
          }
          last.set(p.id,{t:f.time,xy:p.xy,segment:p.segment,player_id:p.player_id,role:p.role,team_id:p.team_id,scope:JSON.stringify(p.source_scope)});
        }
      }
    }
    for (const p of frame.players) {
      if (!p.xy || !visible(p)) continue;
      const px=x(p.xy[0]),py=y(p.xy[1]), player=person(p.player_id);
      ctx.fillStyle=color(p.team_id);ctx.strokeStyle="white";ctx.lineWidth=1.2*pixelRatio;
      ctx.beginPath();ctx.arc(px,py,5*pixelRatio,0,Math.PI*2);ctx.fill();ctx.stroke();
      ctx.fillStyle="#172c40";ctx.font=`${11*pixelRatio}px Segoe UI`;ctx.textAlign="center";
      ctx.fillText(player ? "#"+player.jersey_number : "M"+trackLabels.get(p.id),px,py-9*pixelRatio);
    }
    $("spatialNote").textContent="Vị trí 2D dùng điểm chân đã quan sát; làm mượt hiển thị khi theo dõi liên tục. Heatmap giữ thời gian quan sát gốc, không cộng điểm dự đoán hoặc khoảng mất dấu.";
  }

  function drawHeatmap() {
    const {ctx,x,y,scale,lines,ymax}=court($("matchHeatmap"));
    $('heatLegendMax').textContent = '0 người·giây/ô';
    $('heatmapTotals').textContent = result ? '' : 'Heatmap sẽ xuất hiện khi pipeline cập nhật xong kết quả.';
    if(!result) return;
    const start=Number($("heatStart").value),end=Number($("heatEnd").value),filter=$("spatialFilter").value;
    if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start || end > duration+.001) {
      $('heatmapTotals').textContent = 'Chọn khoảng thời gian hợp lệ trong video.'; return;
    }
    const [rows, cols] = result.grid_shape || [44,60];
    let grid=result.heatmaps[filter];
    if(start>0 || end<duration) {
      grid=Array.from({length:rows},()=>Array(cols).fill(0));
      if(!Array.isArray(result.heatmap_intervals)) {
        say("Hãy cập nhật bản đồ sân để lọc heatmap theo thời gian.");
        return;
      }
      const intervals = filter === 'unknown_role' ? result.unknown_heatmap_intervals || [] : result.heatmap_intervals;
      for(const [a,b,row,col,track,team,player] of intervals) {
        const dt=Math.min(end,b)-Math.max(start,a);
        if(dt>0 && (filter==="all" || filter==='unknown_role' || (filter==='unknown_team'&&!team) || filter==="track:"+track || filter==="team:"+team || filter==="player:"+player)) grid[row][col]+=dt;
      }
    }
    if(!grid) { $('heatmapTotals').textContent = 'Chưa có thời gian hiện diện hợp lệ cho lựa chọn này.'; return; }
    const peak=Math.max(0,...grid.flat());
    const total=grid.flat().reduce((sum,v)=>sum+v,0), percent=$('heatScale').value==='percent';
    const reference=result.heatmaps[filter==='unknown_role'?'unknown_role':'all'] || grid;
    const maximum=percent?100:Math.max(0,...reference.flat());
    $('heatLegendMax').textContent = percent ? '100% tổng thời gian đã quan sát' : `${maximum.toFixed(2)} người·giây/ô`;
    const cell=result.cell_size_xy || [15/cols,ymax/rows];
    $('heatmapTotals').textContent = `${total.toFixed(2)} ${filter==='unknown_role'?'người':'cầu thủ'}·giây · Ô ${cell[0].toFixed(2)} × ${cell[1].toFixed(2)} m. ${percent?'Phân bố của lựa chọn hiện tại.':'Thang chung cho các đội và khoảng thời gian.'}`;
    if(peak<=0) { $('heatmapTotals').textContent += ' Chưa có interval hợp lệ.'; return; }
    for(let row=0;row<grid.length;row++) for(let col=0;col<grid[row].length;col++) {
      const mass=grid[row][col]; if(mass<=0) continue;
      const value=percent?mass/total*100:mass, intensity=Math.sqrt(value/Math.max(maximum,1e-12));
      ctx.fillStyle=`rgba(180,44,21,${Math.min(.95,.08+.87*intensity)})`;
      ctx.fillRect(x(-7.5+col*15/cols),y((row+1)*ymax/rows),15/cols*scale+.25,ymax/rows*scale+.25);
    }
    lines();
  }

  for(const id of ["rosterA","rosterB","teamAName","teamBName"]) $(id).addEventListener("change",()=>{try{collectForm();playerOptions();renderLists();draw();drawOverlay();}catch(e){say(e.message);}});
  $("addAssignment").onclick=()=>{
    if(!config) return;
    try {
      collectForm();
      const track=selectedTrack,target=$("assignmentPlayer").value;
      if(!track||!target) throw new Error("Chọn một mã theo dõi và đội hoặc cầu thủ.");
      const trackData=trackCatalog.find(t=>t.id===track);
      if(!trackData) throw new Error("Không tìm thấy mã theo dõi trong kết quả hiện tại.");
      const pid=target.startsWith("player:") ? target.slice(7) : null;
      const full=$('assignmentScope').value==='track';
      const start=full?trackData.start_s:Number($('assignmentStart').value),end=full?Math.min(duration,trackData.end_s+.001):Number($('assignmentEnd').value);
      if (!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start||end>duration) throw new Error('Khoảng gán phải nằm trong video và có độ dài dương.');
      const retained=[];
      for(const a of config.assignments){
        if(a.track_id!==track||a.end_s<=start||a.start_s>=end)retained.push(a);
        else {if(a.start_s<start)retained.push({...a,end_s:start});if(a.end_s>end)retained.push({...a,start_s:end});}
      }
      config.assignments=retained;
      config.assignments.push({track_id:track,player_id:pid,team_id:pid ? person(pid).team_id : target.startsWith("team:") ? target.slice(5) : null,role:target==="non_player"?"non_player":target==="referee"?"referee":"player",start_s:start,end_s:end});
      result=null;renderLists();draw();drawHeatmap();drawOverlay();say("Đã cập nhật khoảng gán. Lưu thiết lập và cập nhật bản đồ sân.");
    } catch(e) {say(e.message);}
  };
  $("pickTrack").onclick=()=>{
    if(!trackCatalog.length&&!overlays.some(f=>f.boxes.some(p=>p.id))) {say("Phân tích video trước để chọn mã theo dõi.");return;}
    picking=!picking;video.pause();canvas.style.pointerEvents=picking?"auto":"none";
    $("pickTrack").textContent=picking?"Bấm vào box cần chọn…":"Chọn box ở khung hình đang dừng";
  };
  canvas.addEventListener("click",e=>{
    if(!picking) return;
    const b=canvas.getBoundingClientRect(),s=Math.min(b.width/video.videoWidth,b.height/video.videoHeight),dx=(b.width-video.videoWidth*s)/2,dy=(b.height-video.videoHeight*s)/2;
    const px=(e.clientX-b.left-dx)/s,py=(e.clientY-b.top-dy)/s;
    const boxes=OverlayPlayback.boxesAt(overlays,video.currentTime);
    const found=boxes.filter(p=>p.id&&trackVisible(p.id,video.currentTime,p)&&px>=p.box[0]&&px<=p.box[2]&&py>=p.box[1]&&py<=p.box[3]).sort((a,b)=>(a.box[2]-a.box[0])*(a.box[3]-a.box[1])-(b.box[2]-b.box[0])*(b.box[3]-b.box[1]))[0];
    if(found){
      // Stale spatial maps still have valid source bboxes. A video-wide
      // assignment covers this track wherever it is actually observed.
      if(!trackCatalog.some(t=>t.id===found.id)) trackCatalog.push({id:found.id,start_s:0,end_s:duration});
      selectedTrack=found.id;
      $("assignmentTrack").value=found.id;
      $("selectedTrackNote").textContent=`Đã chọn mã ${trackLabels.get(found.id)||found.id} tại ${time(video.currentTime)}.`;
      $("addAssignment").disabled=false;
      $('assignmentStart').value=video.currentTime.toFixed(3);
      $('assignmentEnd').value=Math.min(duration,video.currentTime+1).toFixed(3);
      picking=false;canvas.style.pointerEvents="none";
      $("pickTrack").textContent="Chọn box ở khung hình đang dừng";
      say("Chọn cầu thủ hoặc vai trò và kiểm tra khoảng thời gian trước khi áp dụng.");
    }
  });

  async function save(rebuild) {
    if(!config||pending) return;
    const id=loadedJob,serial=requestSerial;
    pending=true;$("saveMatch").disabled=$("rebuildMatch").disabled=true;
    try {
      say("Đang lưu thiết lập…");
      const saved=await postJson("/api/configure",{...collectForm(),_expected_revision:savedRevision});
      if(serial!==requestSerial||id!==jobId) return;
      config=saved.config;savedRevision=saved.revision;result=null;loadCalibrationEditor();playerOptions();renderLists();drawHeatmap();draw();drawOverlay();
      activeRebuild=saved.spatial?.status==='running';
      updateMappingNote();
      if(activeRebuild) say('Đã lưu. Đang tự cập nhật nhãn, bản đồ và heatmap…');
      else say('Đã lưu thông tin đội. Bấm Phân tích để bắt đầu pipeline tự động.');
    }catch(e){if(serial===requestSerial)say(e.message);}
    finally{pending=false;if(serial===requestSerial){$("saveMatch").disabled=false;$("rebuildMatch").disabled=jobStatus!=="completed";}}
  }
  $("saveMatch").onclick=()=>save(false);
  $('assignmentScope').onchange=()=>{
    const full=$('assignmentScope').value==='track';
    $('assignmentStartLabel').hidden=$('assignmentEndLabel').hidden=full;
    $('addAssignment').textContent=full?'Áp dụng cho toàn mã':'Áp dụng khoảng gán';
  };
  $("rebuildMatch").onclick=()=>save(true);
  for(const id of ["spatialFilter","heatStart","heatEnd","heatScale"]) $(id).addEventListener("change",()=>{drawHeatmap();draw();});
  $("showTrails").onchange=draw;
  let polling=false;
  setInterval(async()=>{
    if(!loadedJob||polling||pending||jobStatus!=='completed')return;
    const id=loadedJob,serial=requestSerial;polling=true;
    try {
      const state=await api("/api/spatial/status",{},id);
      if(serial!==requestSerial) return;
      if(state.status==="completed" && (activeRebuild||state.revision!==result?.revision)){
        const data=await api('/api/match',{},id);
        if(serial!==requestSerial)return;
        config=data.config;savedRevision=data.revision;fillForm();activeRebuild=false;await fetchResult(id,serial);
      }
      else if(state.status==="failed"){activeRebuild=false;$('rebuildMatch').hidden=false;say(state.error||'Không cập nhật được kết quả. Bấm Thử cập nhật lại.');}
      else if(state.status==="running"){
        activeRebuild=true;
        say(state.stage==='jersey_identity' ? `Đang đọc số áo để đối chiếu tên cầu thủ${state.total ? ` (${state.count}/${state.total} crop)` : ' — khởi tạo OCR'}…` : 'Đang tự cập nhật kết quả…');
      }
      else if(state.status==='stale'&&!activeRebuild){
        await api('/api/rebuild',{method:'POST',headers:{'X-Demo-Request':'1'}},id);activeRebuild=true;
      }
    }catch(e){if(serial===requestSerial)say(e.message);}finally{polling=false;}
  },1500);
  const teamColor = (track, t = video.currentTime, snapshot = null) => {
    if(!config) return null;
    const mapping=assignmentFor(track,t);
    if(mapping) {
      if(mapping.role === "referee") return "#94a3b8";
      if(mapping.role === "non_player") return "#64748b";
      return color(mapping.team_id);
    }
    const p=frameAt(t)?.players.find(p=>p.id===track) || snapshot;
    if(p?.role === "referee") return "#94a3b8";
    const tid = p?.team_id || result?.color_teams?.[track];
    return tid ? color(tid) : null;
  };
  const trackVisible = (track, t = video.currentTime, snapshot = null) =>
    (assignmentFor(track, t) || frameAt(t)?.players.find(p=>p.id===track) || snapshot)?.role !== "non_player";
  window.MatchUI={load,reset,draw,label:shortLabel,reviewedLabel,color:teamColor,visible:trackVisible};
  // Handles a fast restored session that finished before this script loaded.
  if(jobId) load(jobId,generation);
})();
