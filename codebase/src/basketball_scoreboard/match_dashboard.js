/* Match configuration, reviewed track identities and source-time court playback. */
(() => {
  let config = null, result = null, duration = 0, loadedJob = null;
  let picking = false, pending = false, selectedTrack = "";
  let requestSerial = 0, activeRebuild = false;
  const hex = rgb => "#" + rgb.map(v => Math.round(v).toString(16).padStart(2, "0")).join("");
  const rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
  const say = text => { $("matchStatus").textContent = text; };
  const postJson = (path, data) => api(path, {method: "POST", headers: {"X-Demo-Request": "1", "Content-Type": "application/json"}, body: JSON.stringify(data)}, loadedJob);
  const teamName = id => id === config?.roster.team_a_id ? config.roster.team_a_name : id === config?.roster.team_b_id ? config.roster.team_b_name : "Chưa rõ đội";
  const person = id => config?.roster.players.find(p => p.player_id === id);
  const color = id => id === config?.roster.team_a_id ? hex(config.roster.team_a_color_rgb) : id === config?.roster.team_b_id ? hex(config.roster.team_b_color_rgb) : "#64748b";
  const assignmentFor = (track, t = video.currentTime) =>
    config?.assignments.find(a => a.track_id === track && a.start_s <= t && t < a.end_s);
  const shortLabel = track => {
    if (!config) return null;
    const t = video.currentTime;
    const mapping = assignmentFor(track, t);
    if (mapping) {
      if (mapping.role === "non_player") return "Ngoài sân";
      const p = person(mapping.player_id);
      return p ? `#${p.jersey_number} ${p.name}` : teamName(mapping.team_id);
    }
    const frame = frameAt(t);
    const item = frame?.players.find(p => p.id === track);
    const p = person(item?.player_id);
    if (p) return `#${p.jersey_number} ${p.name}`;
    const tid = item?.team_id || result?.color_teams?.[track];
    if (tid) return teamName(tid);
    return null;
  };

  function reset() {
    requestSerial++;
    config = result = null;
    loadedJob = null;
    selectedTrack = "";
    activeRebuild = false;
    picking = false;
    canvas.style.pointerEvents = "none";
    $("pickTrack").textContent = "Chọn người trên video";
    $("selectedTrackNote").textContent = "Chưa chọn mã theo dõi.";
    $("addAssignment").disabled = true;
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
    for (const [id, label] of [["", "Chọn đội / cầu thủ"], ["non_player", "Ngoài sân / không phải cầu thủ"], ["team:"+config.roster.team_a_id, config.roster.team_a_name], ["team:"+config.roster.team_b_id, config.roster.team_b_name], ...config.roster.players.map(p => ["player:"+p.player_id, `${teamName(p.team_id)} · #${p.jersey_number} ${p.name}`])]) {
      $("assignmentPlayer").add(new Option(label, id));
    }
    $("assignmentPlayer").value = value;
  }

  function renderLists() {
    for (const [field, list, label] of [
      ["assignmentList", config.assignments, s => {
        const track = result?.tracks.find(t => t.id === s.track_id);
        const coversTrack = track && s.start_s <= track.start_s && s.end_s >= Math.min(duration, track.end_s + .001);
        const scope = coversTrack ? "toàn mã" : `${time(s.start_s)}–${time(s.end_s)}`;
        return `${trackLabels.has(s.track_id) ? "Mã "+trackLabels.get(s.track_id) : s.track_id} → ${s.role === "non_player" ? "Ngoài sân" : person(s.player_id)?.name || teamName(s.team_id)} · ${scope}`;
      }],
    ]) {
      $(field).replaceChildren();
      list.forEach((s, i) => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label(s) + " ×";
        button.title = "Bỏ gán này";
        button.onclick = () => { list.splice(i, 1); renderLists(); drawOverlay(); say("Có thay đổi chưa lưu."); };
        $(field).append(button);
      });
    }
  }

  async function load(id, token) {
    if (!id) { reset(); return; }
    const serial = ++requestSerial;
    try {
      const data = await api("/api/match", {}, id);
      if (serial !== requestSerial || token !== generation || id !== jobId) return;
      loadedJob = id; config = data.config; duration = data.duration_s; result = null;
      fillForm();
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
      } else say(data.spatial.status === "stale" ? "Thiết lập đã đổi. Hãy cập nhật bản đồ sân." : "Nhập đội hình và đánh dấu sân để dựng bản đồ.");
    } catch (e) { if (serial === requestSerial) say(e.message); }
  }

  async function fetchResult(id, serial) {
    const data = await api("/api/spatial", {}, id);
    if (serial !== requestSerial || id !== jobId) return;
    if (data.status !== "completed") { say("Kết quả cần được cập nhật."); return; }
    result = data;
    $("assignmentTrack").replaceChildren(new Option("Chọn mã theo dõi", ""));
    for (const tr of data.tracks) {
      if (!trackLabels.has(tr.id)) trackLabels.set(tr.id, trackLabels.size+1);
      $("assignmentTrack").add(new Option(`Mã ${trackLabels.get(tr.id)} · ${time(tr.start_s)}–${time(tr.end_s)}`, tr.id));
    }
    const filter = $("spatialFilter");
    filter.replaceChildren(new Option("Tất cả", "all"));
    for (const team of [config.roster.team_a_id, config.roster.team_b_id]) filter.add(new Option(teamName(team), "team:"+team));
    for (const p of config.roster.players) filter.add(new Option(`#${p.jersey_number} ${p.name}`, "player:"+p.player_id));
    for (const tr of data.tracks) if (data.heatmaps["track:"+tr.id]) filter.add(new Option(`Mã ${trackLabels.get(tr.id)}`, "track:"+tr.id));
    renderLists();
    drawHeatmap(); draw(); drawOverlay();
    say("Bản đồ 2D và heatmap đã được dựng từ các vị trí sân hợp lệ.");
  }

  function frameAt(t) {
    if (!result?.frames.length) return null;
    const frames = result.frames;
    let lo = 0, hi = frames.length-1, index = -1;
    while (lo <= hi) { const mid = (lo+hi)>>1; if (frames[mid].time <= t+.001) { index=mid; lo=mid+1; } else hi=mid-1; }
    return index >= 0 && t-frames[index].time <= .3 ? frames[index] : null;
  }
  const visible = p => {
    const f = $("spatialFilter").value;
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
      ctx.strokeRect(x(-7.5), y(ymax), 15*scale, ymax*scale);
      const end = flip => {
        const yy = v => y(flip ? ymax-v : v);
        ctx.strokeRect(x(-2.45), Math.min(yy(0),yy(5.8)), 4.9*scale, 5.8*scale);
        ctx.beginPath(); ctx.arc(x(0),yy(5.8),1.8*scale,0,Math.PI*2); ctx.stroke();
        ctx.beginPath(); ctx.arc(x(0),yy(1.575),6.75*scale,flip ? 0 : Math.PI,flip ? Math.PI : Math.PI*2); ctx.stroke();
        ctx.strokeStyle="#d17a25";ctx.beginPath();ctx.arc(x(0),yy(1.575),.23*scale,0,Math.PI*2);ctx.stroke();ctx.strokeStyle="#a08d71";
      };
      ctx.save();ctx.beginPath();ctx.rect(x(-7.5),y(ymax),15*scale,ymax*scale);ctx.clip();end(false);
      if(ymax>15) {end(true);ctx.beginPath();ctx.moveTo(x(-7.5),y(ymax/2));ctx.lineTo(x(7.5),y(ymax/2));ctx.stroke();ctx.beginPath();ctx.arc(x(0),y(ymax/2),1.8*scale,0,Math.PI*2);ctx.stroke();}
      ctx.restore();
    };
    lines();
    return {ctx,x,y,scale,lines,ymax};
  }

  function draw() {
    if (!config) return;
    const {ctx,x,y} = court($("courtCanvas")), t=video.currentTime, frame=frameAt(t);
    $("spatialTime").textContent=time(t);
    if (!frame?.players.some(p=>p.xy)) {
      $("spatialNote").textContent = "Chưa có tọa độ sân hợp lệ. Hãy hiệu chuẩn sân để hiển thị vị trí 2D và heatmap.";
      return;
    }
    if ($("showTrails").checked) {
      const last = new Map();
      for (const f of result.frames) {
        if (f.time < t-3) continue;
        if (f.time > t) break;
        for (const p of f.players) {
          if (!p.xy || !visible(p)) continue;
          const old=last.get(p.id);
          if(old && f.time-old.t<=.3 && uninterrupted(old.t,f.time) && f.segment===old.segment && Math.hypot(p.xy[0]-old.xy[0],p.xy[1]-old.xy[1])<=12*(f.time-old.t)) {
            ctx.strokeStyle=color(p.team_id);ctx.globalAlpha=.4;ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x(old.xy[0]),y(old.xy[1]));ctx.lineTo(x(p.xy[0]),y(p.xy[1]));ctx.stroke();ctx.globalAlpha=1;
          }
          last.set(p.id,{t:f.time,xy:p.xy,segment:f.segment});
        }
      }
    }
    for (const p of frame.players) {
      if (!p.xy || !visible(p)) continue;
      const px=x(p.xy[0]),py=y(p.xy[1]), player=person(p.player_id);
      ctx.fillStyle=color(p.team_id);ctx.strokeStyle="white";ctx.lineWidth=2;
      ctx.beginPath();ctx.arc(px,py,9,0,Math.PI*2);ctx.fill();ctx.stroke();
      ctx.fillStyle="#172c40";ctx.font="13px Segoe UI";ctx.textAlign="center";
      ctx.fillText(player ? "#"+player.jersey_number : "M"+trackLabels.get(p.id),px,py-14);
    }
    $("spatialNote").textContent="Vị trí 2D dùng điểm chân của quan sát hợp lệ. Các khoảng mất dấu và vị trí dự đoán không được nối vào heatmap.";
  }

  function drawHeatmap() {
    const {ctx,x,y,scale,lines,ymax}=court($("matchHeatmap"));
    if(!result) return;
    const start=Number($("heatStart").value),end=Number($("heatEnd").value),filter=$("spatialFilter").value;
    let grid=result.heatmaps[filter];
    if(start>0 || end<duration) {
      grid=Array.from({length:44},()=>Array(60).fill(0));
      if(!Array.isArray(result.heatmap_intervals)) {
        say("Hãy cập nhật bản đồ sân để lọc heatmap theo thời gian.");
        return;
      }
      for(const [a,b,row,col,track,team,player] of result.heatmap_intervals) {
        const dt=Math.min(end,b)-Math.max(start,a);
        if(dt>0 && (filter==="all" || filter==="track:"+track || filter==="team:"+team || filter==="player:"+player)) grid[row][col]+=dt;
      }
    }
    if(!grid) return;
    const peak=Math.max(0,...grid.flat());
    if(peak<=0) return;
    for(let row=0;row<grid.length;row++) for(let col=0;col<grid[row].length;col++) {
      const mass=grid[row][col]; if(mass<=0) continue;
      ctx.fillStyle=`rgba(207,87,26,${.12+.76*Math.sqrt(mass/peak)})`;
      ctx.fillRect(x(-7.5+col*15/60),y((row+1)*ymax/44),15/60*scale+.5,ymax/44*scale+.5);
    }
    lines();
  }

  for(const id of ["rosterA","rosterB","teamAName","teamBName"]) $(id).addEventListener("change",()=>{try{collectForm();playerOptions();}catch(e){say(e.message);}});
  $("addAssignment").onclick=()=>{
    if(!config) return;
    try {
      collectForm();
      const track=selectedTrack,target=$("assignmentPlayer").value;
      if(!track||!target) throw new Error("Chọn một mã theo dõi và đội hoặc cầu thủ.");
      const trackData=result?.tracks.find(t=>t.id===track);
      if(!trackData) throw new Error("Không tìm thấy mã theo dõi trong kết quả hiện tại.");
      const pid=target.startsWith("player:") ? target.slice(7) : null;
      config.assignments = config.assignments.filter(a => a.track_id !== track);
      config.assignments.push({track_id:track,player_id:pid,team_id:pid ? person(pid).team_id : target.startsWith("team:") ? target.slice(5) : null,role:target==="non_player"?"non_player":"player",start_s:trackData.start_s,end_s:Math.min(duration,trackData.end_s+.001)});
      renderLists();drawOverlay();say("Đã gán cho toàn mã theo dõi. Lưu thiết lập để áp dụng.");
    } catch(e) {say(e.message);}
  };
  $("pickTrack").onclick=()=>{
    if(!result) {say("Phân tích video trước để chọn mã theo dõi.");return;}
    picking=!picking;video.pause();canvas.style.pointerEvents=picking?"auto":"none";
    $("pickTrack").textContent=picking?"Bấm vào box cần chọn…":"Chọn box ở khung hình đang dừng";
  };
  canvas.addEventListener("click",e=>{
    if(!picking) return;
    const b=canvas.getBoundingClientRect(),s=Math.min(b.width/video.videoWidth,b.height/video.videoHeight),dx=(b.width-video.videoWidth*s)/2,dy=(b.height-video.videoHeight*s)/2;
    const px=(e.clientX-b.left-dx)/s,py=(e.clientY-b.top-dy)/s;
    let nearest=null;
    for(const f of overlays){if(f.time<=video.currentTime)nearest=f;else break;}
    if(!nearest||video.currentTime-nearest.time>.3) return;
    const found=nearest.boxes.filter(p=>p.id&&px>=p.box[0]&&px<=p.box[2]&&py>=p.box[1]&&py<=p.box[3]).sort((a,b)=>(a.box[2]-a.box[0])*(a.box[3]-a.box[1])-(b.box[2]-b.box[0])*(b.box[3]-b.box[1]))[0];
    if(found){
      selectedTrack=found.id;
      $("assignmentTrack").value=found.id;
      $("selectedTrackNote").textContent=`Đã chọn mã ${trackLabels.get(found.id)||found.id} tại ${time(video.currentTime)}.`;
      $("addAssignment").disabled=false;
      picking=false;canvas.style.pointerEvents="none";
      $("pickTrack").textContent="Chọn box ở khung hình đang dừng";
      say("Chọn cầu thủ hoặc ngoài sân rồi áp dụng cho toàn mã theo dõi.");
    }
  });

  async function save(rebuild) {
    if(!config||pending) return;
    const id=loadedJob,serial=requestSerial;
    pending=true;$("saveMatch").disabled=$("rebuildMatch").disabled=true;
    try {
      say("Đang lưu thiết lập…");
      const saved=await postJson("/api/configure",collectForm());
      if(serial!==requestSerial||id!==jobId) return;
      config=saved.config;result=null;drawHeatmap();draw();
      if(rebuild){await api("/api/rebuild",{method:"POST",headers:{"X-Demo-Request":"1"}},id);activeRebuild=true;say("Đang cập nhật bản đồ từ tracking đã lưu…");}
      else say("Đã lưu. Hãy cập nhật bản đồ sân để áp dụng thiết lập.");
    }catch(e){if(serial===requestSerial)say(e.message);}
    finally{pending=false;if(serial===requestSerial){$("saveMatch").disabled=false;$("rebuildMatch").disabled=jobStatus!=="completed";}}
  }
  $("saveMatch").onclick=()=>save(false);
  $("rebuildMatch").onclick=()=>save(true);
  for(const id of ["spatialFilter","heatStart","heatEnd"]) $(id).addEventListener("change",()=>{drawHeatmap();draw();});
  $("showTrails").onchange=draw;
  let polling=false;
  setInterval(async()=>{
    if(!activeRebuild||!loadedJob||polling)return;
    const id=loadedJob,serial=requestSerial;polling=true;
    try {
      const state=await api("/api/spatial/status",{},id);
      if(serial!==requestSerial) return;
      if(state.status==="completed"){activeRebuild=false;await fetchResult(id,serial);}
      else if(state.status==="failed"){activeRebuild=false;say(state.error);}
      else if(state.status==="running")say("Đang dựng bản đồ sân…");
      else {activeRebuild=false;say("Thiết lập đã đổi. Hãy cập nhật lại bản đồ.");}
    }catch(e){if(serial===requestSerial)say(e.message);}finally{polling=false;}
  },1500);
  const teamColor = track => {
    if(!config) return null;
    const t=video.currentTime,mapping=assignmentFor(track,t);
    if(mapping)return color(mapping.team_id);
    const p=frameAt(t)?.players.find(p=>p.id===track);
    const tid = p?.team_id || result?.color_teams?.[track];
    return tid ? color(tid) : null;
  };
  const trackVisible = track => assignmentFor(track)?.role !== "non_player";
  window.MatchUI={load,reset,draw,label:shortLabel,color:teamColor,visible:trackVisible};
  // Handles a fast restored session that finished before this script loaded.
  if(jobId) load(jobId,generation);
})();
