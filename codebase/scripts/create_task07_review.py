#!/usr/bin/env python3
"""Create a source-only annotation review page; never reads inference outputs."""
import argparse
import html
import json
import os
from pathlib import Path
import sys
from urllib.parse import quote

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.spatial_io import file_hash,new_output,write_json
from basketball_scoreboard.video import VideoReader,probe_video


def color_proposals(image):
    hsv=cv2.cvtColor(image,cv2.COLOR_BGR2HSV)
    mask=((hsv[:,:,0]>=18)&(hsv[:,:,0]<=45)&(hsv[:,:,1]>95)&(hsv[:,:,2]>75)).astype(np.uint8)*255
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    options=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour);area=cv2.contourArea(contour);perimeter=cv2.arcLength(contour,True)
        if 7<=max(w,h)<=65 and min(w,h)>=4 and .35<=w/h<=2.8 and area/(w*h)>.2 and perimeter:
            circularity=4*np.pi*area/perimeter**2
            if circularity>.2:options.append((circularity/(1+abs(max(w,h)-20)/20),[max(0,x-2),max(0,y-2),min(image.shape[1],x+w+2),min(image.shape[0],y+h+2)]))
    return [box for _,box in sorted(options,key=lambda x:-x[0])[:6]]


PAGE=r'''<!doctype html><meta charset="utf-8"><title>Task07 — source annotation review</title>
<style>body{font:15px Segoe UI,sans-serif;background:#f5f4ef;color:#172425;margin:24px;max-width:1400px}h1{font-size:25px}button,input,select{font:inherit;padding:7px;margin:4px}button{cursor:pointer}canvas{max-width:100%;border:1px solid #aaa;background:#111}video{max-width:100%;width:800px}textarea{width:100%;height:200px}fieldset{margin-top:16px;border:1px solid #b4bfba}.note{background:#fff3cf;padding:12px}#status{font-weight:bold}.row{display:flex;flex-wrap:wrap;gap:12px}label{display:inline-block}</style>
<h1>Task07 — review nhãn từ video gốc</h1>
<p class="note">Roster và protocol đã được duyệt. Nhãn dưới đây là draft, cần bạn kiểm tra. Các ô màu gợi ý chỉ từ HSV của ảnh gốc, không phải prediction detector và không phải ground truth. Không duyệt khi chưa xem đoạn video/uncertain cases.</p>
<video id="video" controls preload="metadata" src="VIDEO_URL"></video>
<p><button onclick="stepFrame(-1)">Video −1 frame</button><button onclick="stepFrame(1)">Video +1 frame</button></p>
<p id="status"></p><button onclick="change(-1)">← Mẫu trước</button><button onclick="change(1)">Mẫu sau →</button>
<label>Mẫu <input id="index" type="number" min="0" value="0" onchange="show()" style="width:70px"></label>
<button onclick="video.currentTime=current().source_time_s;video.pause()">Video tới mẫu</button>
<button onclick="accept(true)">Bóng nhìn thấy — duyệt bbox</button><button onclick="accept(false)">Bóng bị che/ngoài khung</button>
<button onclick="uncertain()">Giữ uncertain</button>
<p>Vẽ bbox trên ảnh hoặc chọn một gợi ý: <span id="candidates"></span></p><canvas id="canvas"></canvas>
<fieldset><legend>Control interval draft</legend><input id="cs" type="number" step="0.033333" placeholder="start (s)"><button onclick="takeTime('cs')">Lấy start từ video</button><input id="ce" type="number" step="0.033333" placeholder="end (s)"><button onclick="takeTime('ce')">Lấy end từ video</button><select id="ca"></select><button onclick="addControl()">Thêm interval</button></fieldset>
<fieldset><legend>Completed pass draft</legend><input id="pr" type="number" step="0.033333" placeholder="release (s)"><button onclick="takeTime('pr')">Lấy release</button><input id="pc" type="number" step="0.033333" placeholder="receive (s)"><button onclick="takeTime('pc')">Lấy receive</button><select id="pa"></select><select id="pb"></select><button onclick="addPass()">Thêm pass</button></fieldset>
<p>Thời gian trong hai form là giây của đoạn nhỏ, không phải game clock. Xem video quanh release/receive, không lấy timeline prediction để gán nhãn. Danh sách actor và khoảng uncertain có thể sửa trong JSON.</p>
<button onclick="refreshEditor()">Hiện JSON hiện tại</button><button onclick="applyEditor()">Áp dụng JSON sửa</button><textarea id="editor"></textarea>
<p><label>Reviewer <input id="reviewer" placeholder="Tên/ID người review"></label><label><input type="checkbox" id="coverageReviewed">Tôi đã xem toàn bộ coverage được chấm, gồm cả đoạn không có pass</label></p>
<button onclick="download(false)">Tải draft JSON</button><button onclick="download(true)">Xuất packet đã review</button>
<label>Nạp draft/packet <input type="file" accept=".json" onchange="loadFile(event)"></label>
<script>
let data=PACKET_JSON; const roster=ROSTER_JSON; const frames=FRAME_URLS;
const video=document.getElementById('video'),canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d');let image=new Image(),drag=null;
for(const id of ['ca','pa','pb']){let empty=document.createElement('option');empty.value='';empty.textContent='Chọn cầu thủ';document.getElementById(id).appendChild(empty);for(const p of roster.players){let o=document.createElement('option');o.value=p.player_id;o.textContent=p.team_id+' #'+p.jersey_number+' '+p.name;document.getElementById(id).appendChild(o)}}
function stepFrame(delta){video.pause();video.currentTime=Math.max(0,Math.min(video.duration||30,video.currentTime+delta/(data.nominal_fps||30)))}
function takeTime(id){document.getElementById(id).value=video.currentTime.toFixed(6)}
function current(){return data.ball_samples[Number(document.getElementById('index').value)]}
function change(delta){let e=document.getElementById('index');e.value=Math.max(0,Math.min(data.ball_samples.length-1,Number(e.value)+delta));show()}
function show(){const s=current();if(!s)return;canvas.width=data.original_wh[0];canvas.height=data.original_wh[1];image.onload=draw;image.src=frames[s.frame_index];document.getElementById('status').textContent='t='+s.source_time_s.toFixed(3)+'s | parent='+ (data.parent_time_offset_s+s.source_time_s).toFixed(3)+'s | '+(s.reviewed?'reviewed':'needs review');let holder=document.getElementById('candidates');holder.replaceChildren();(s.annotation_candidates||[]).forEach((b,i)=>{let e=document.createElement('button');e.textContent=String(i+1);e.onclick=()=>{s.xyxy=b.slice();draw()};holder.appendChild(e)})}
function draw(){ctx.drawImage(image,0,0);const b=current().xyxy;if(b){ctx.strokeStyle='#ffdf00';ctx.lineWidth=3;ctx.strokeRect(b[0],b[1],b[2]-b[0],b[3]-b[1])}}
function point(event){const r=canvas.getBoundingClientRect();return [(event.clientX-r.left)*canvas.width/r.width,(event.clientY-r.top)*canvas.height/r.height]}
canvas.onpointerdown=e=>{drag=point(e);canvas.setPointerCapture(e.pointerId)};canvas.onpointerup=e=>{if(!drag)return;const p=point(e);current().xyxy=[Math.max(0,Math.min(drag[0],p[0])),Math.max(0,Math.min(drag[1],p[1])),Math.min(canvas.width,Math.max(drag[0],p[0])),Math.min(canvas.height,Math.max(drag[1],p[1]))].map(Math.round);current().reviewed=false;drag=null;draw()};
function accept(visible){const s=current();if(visible&&(!s.xyxy||s.xyxy[2]<=s.xyxy[0]||s.xyxy[3]<=s.xyxy[1]))return alert('Cần bbox hợp lệ');s.visible=visible;s.uncertain=false;s.reviewed=true;change(1)}
function uncertain(){const s=current();s.uncertain=true;s.reviewed=true;change(1)}
function getActor(id){const p=roster.players.find(x=>x.player_id===document.getElementById(id).value);if(!p)throw Error('Chọn cầu thủ trước khi lưu');return {player_id:p.player_id,team_id:p.team_id}}
function number(id){const x=document.getElementById(id).value;if(x==='')throw Error('Thiếu thời gian');const n=Number(x);if(!Number.isFinite(n)||n<0)throw Error('Thời gian không hợp lệ');return n}
function addControl(){try{const a=number('cs'),b=number('ce');if(b<=a)throw Error('end phải lớn hơn start');data.control_intervals.push({start_time_s:a,end_time_s:b,...getActor('ca'),uncertain:false,reviewed:true});refreshEditor()}catch(e){alert(e.message)}}
function addPass(){try{const a=number('pr'),b=number('pc');if(b<a)throw Error('receive phải sau release');data.passes.push({pass_id:'review_pass_'+(data.passes.length+1),release_time_s:a,receive_time_s:b,passer:getActor('pa'),receiver:getActor('pb'),uncertain:false,reviewed:true});refreshEditor()}catch(e){alert(e.message)}}
function refreshEditor(){document.getElementById('editor').value=JSON.stringify(data,null,2)}
function applyEditor(){try{const x=JSON.parse(document.getElementById('editor').value);if(x.source_video_sha256!==data.source_video_sha256)throw Error('Sai video');data=x;show()}catch(e){alert(e.message)}}
function download(approve){let x=structuredClone(data);x.review_status='draft';if(approve){let r=document.getElementById('reviewer').value.trim();if(!r||!document.getElementById('coverageReviewed').checked)return alert('Cần reviewer và xác nhận đã xem coverage');if(x.ball_samples.some(s=>!s.reviewed))return alert('Còn ball samples chưa review');if([...x.control_intervals,...x.passes].some(s=>!s.reviewed))return alert('Còn control/pass draft chưa review');x.review_status='approved';x.reviewer=r;x.reviewed_utc=new Date().toISOString()}const blob=new Blob([JSON.stringify(x,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=(approve?'reviewed-':'draft-')+data.video_id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
function loadFile(event){const f=event.target.files[0];if(!f)return;let reader=new FileReader();reader.onload=()=>{try{let x=JSON.parse(reader.result);if(x.source_video_sha256!==data.source_video_sha256)throw Error('Sai video');data=x;show();refreshEditor()}catch(e){alert(e.message)}};reader.readAsText(f)}
show();refreshEditor();
</script>'''


def create(video,roster,policy_path,output_dir,offset_s,sample_every_s=.4):
    video=Path(video).resolve();roster=Path(roster).resolve()
    policy=json.loads(Path(policy_path).read_text(encoding='utf-8'));meta=probe_video(video)
    if policy['source_video_sha256']!=meta.sha256:raise ValueError('Policy source mismatch')
    if sample_every_s<=0:raise ValueError('Positive sampling interval required')
    out=new_output(output_dir,[video,roster,policy_path]);(out/'frames').mkdir()
    samples=[];urls={};next_time=0.;clock=[]
    with VideoReader(video) as reader:
        for frame,image in reader.frames():
            t=frame.source_time_s;clock.append(t)
            if t+1e-6<next_time:continue
            next_time=t+sample_every_s
            if any(i['start_time_s']<=t<i['end_time_s'] for i in policy['intervals']):continue
            filename=f'frames/frame_{frame.frame_index:06d}.jpg'
            if not cv2.imwrite(str(out/filename),image):raise OSError('Cannot save source sample')
            proposals=color_proposals(image)
            samples.append(dict(frame_index=frame.frame_index,source_time_s=t,xyxy=proposals[0] if proposals else None,
                                visible=True,uncertain=True,reviewed=False,annotation_candidates=proposals,
                                annotation_method='source-only HSV proposals; requires human correction/review; not detector predictions'))
            urls[frame.frame_index]=filename
    coverage=[];start=0.
    for item in sorted(policy['intervals'],key=lambda i:i['start_time_s']):
        if start<item['start_time_s']:coverage.append(dict(start_time_s=start,end_time_s=item['start_time_s']))
        start=max(start,item['end_time_s'])
    if start<meta.duration_s:coverage.append(dict(start_time_s=start,end_time_s=meta.duration_s))
    packet=dict(schema_version='task07-evaluation-1',source_video_sha256=meta.sha256,video_id=meta.video_id,
                is_synthetic=False,review_status='draft',reviewer=None,protocol_status='approved',
                protocol_version='task07-vietnam-tonga-20261104',parent_time_offset_s=offset_s,
                original_wh=[meta.width,meta.height],nominal_fps=meta.fps,coverage=coverage,ball_samples=samples,
                control_intervals=[],passes=[],pass_tolerance_s=.25,ball_iou_threshold=.3,
                annotation_note='Not reviewed GT. No inference outputs read; no acceptance metrics until reviewed.')
    write_json(out/'annotations-draft.json',packet)
    safe=lambda x:json.dumps(x,ensure_ascii=False).replace('</','<\\/')
    page=PAGE.replace('VIDEO_URL',html.escape(quote(os.path.relpath(video,out).replace('\\','/')),quote=True))
    page=page.replace('PACKET_JSON',safe(packet)).replace('ROSTER_JSON',safe(json.loads(roster.read_text(encoding='utf-8')))).replace('FRAME_URLS',safe(urls))
    (out/'review.html').write_text(page,encoding='utf-8')
    write_json(out/'review-manifest.json',dict(video_sha256=meta.sha256,roster_sha256=file_hash(roster),sample_count=len(samples),
               status='draft_needs_human_review',source_only=True,inference_outputs_read=False))
    return len(samples)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('video','roster','policy-path','output-dir'):p.add_argument('--'+name,required=True)
    p.add_argument('--offset-s',type=float,required=True);p.add_argument('--sample-every-s',type=float,default=.4)
    args=p.parse_args()
    try:print('Prepared',create(**vars(args)),'source samples; GT review pending')
    except Exception as error:print('Review preparation failed',type(error).__name__,file=sys.stderr);sys.exit(1)
