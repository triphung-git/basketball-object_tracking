#!/usr/bin/env python3
"""Local approved-model annotation suggestions; never export training labels."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import time
import cv2

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from basketball_scoreboard.config import ModelConfig
from basketball_scoreboard.tiled_detection import TiledBallDetector
from basketball_scoreboard.spatial_io import file_hash,new_output,write_json


PAGE=r'''<!doctype html><meta charset="utf-8"><title>Pilot label review</title>
<style>body{font:15px Segoe UI;margin:20px;max-width:1500px}button,input,select{font:inherit;margin:4px;padding:6px}canvas{max-width:100%;border:1px solid #777}textarea{width:100%;height:180px}.note{background:#fff0c5;padding:12px}li{cursor:pointer}</style>
<h1>Pilot annotation review — DRAFT</h1><p class="note">Gợi ý từ model có thể sai. Đối soát đủ ball/human/rim từ ảnh nguồn; không duyệt hàng loạt. Đây là chuẩn bị dữ liệu, chưa train hoặc xuất YOLO labels.</p>
<button onclick="move(-1)">← Trước</button><input id="index" type="number" min="0" value="0" onchange="show()"><button onclick="move(1)">Sau →</button><span id="status"></span>
<p><select id="class"><option>ball</option><option>human</option><option>rim</option></select><button onclick="useSuggestions()">Nạp gợi ý cho ảnh này</button><button onclick="removeBox()">Xóa bbox đang chọn</button><button onclick="clearBoxes()">Xóa toàn bộ bbox ảnh này</button></p>
<canvas id="canvas"></canvas><ul id="boxes"></ul>
<p>Chọn class rồi kéo bbox trên ảnh. Bấm dòng bbox để chọn/xóa; dùng xóa rồi vẽ lại khi cần sửa. Ball thật nhìn thấy phải được gán; hình bóng/người trên poster không phải đối tượng thật.</p>
<select id="scene"><option value="unreviewed">Chọn loại cảnh</option><option value="play">Thi đấu</option><option value="closeup">Cận cảnh</option><option value="replay">Replay</option><option value="background">Background</option></select>
<select id="visibility"><option value="unreviewed">Chọn visibility bóng</option><option value="visible">Bóng nhìn thấy</option><option value="not_visible">Không nhìn thấy bóng</option><option value="uncertain">Không chắc</option></select>
<label><input id="checked" type="checkbox">Đã kiểm tra đủ bbox ball/human/rim trên ảnh nguồn</label><button onclick="approveImage()">Duyệt ảnh</button><button onclick="skipImage()">Bỏ qua ảnh, ghi lý do</button>
<p>Reviewer <input id="reviewer"><button onclick="download(false)">Xuất draft</button><button onclick="download(true)">Xuất packet đã review</button><input type="file" accept=".json" onchange="loadFile(event)"></p>
<button onclick="editor.value=JSON.stringify(data,null,2)">Hiện JSON</button><button onclick="applyEditor()">Áp dụng JSON sửa</button><textarea id="editor"></textarea>
<script>
let data=PACKET_JSON,suggestions=SUGGESTIONS_JSON;
const canvas=document.getElementById('canvas'),ctx=canvas.getContext('2d'),editor=document.getElementById('editor');let image=new Image(),selected=-1,start=null;
function current(){return data.samples[Number(document.getElementById('index').value)]}
function dirty(){current().review_status='unreviewed';data.review_status='draft';document.getElementById('checked').checked=false}
function show(){let el=document.getElementById('index');el.value=Math.max(0,Math.min(data.samples.length-1,Number(el.value)||0));selected=-1;document.getElementById('checked').checked=false;const s=current();document.getElementById('scene').value=s.scene_status;document.getElementById('visibility').value=s.ball_visibility;image.onload=draw;image.src='../'+s.image}
function draw(){const s=current();canvas.width=Math.min(1200,image.naturalWidth);canvas.height=Math.round(image.naturalHeight*canvas.width/image.naturalWidth);ctx.drawImage(image,0,0,canvas.width,canvas.height);const scale=canvas.width/image.naturalWidth,list=document.getElementById('boxes');list.replaceChildren();(s.boxes||[]).forEach((b,i)=>{const [a,c,d,e]=b.xyxy;ctx.strokeStyle=i===selected?'#fff':b.class_name==='ball'?'#00ff51':b.class_name==='human'?'#19a8ff':'#ffb400';ctx.lineWidth=i===selected?3:2;ctx.strokeRect(a*scale,c*scale,(d-a)*scale,(e-c)*scale);const li=document.createElement('li');li.textContent=i+' '+b.class_name+' '+b.xyxy.map(Math.round).join(',');li.onclick=()=>{selected=i;draw()};list.append(li)});document.getElementById('status').textContent=`${s.sample_id} | parent ${s.parent_source_time_s.toFixed(3)}s | ${s.review_status} | ${data.samples.filter(x=>['approved','skipped'].includes(x.review_status)).length}/${data.samples.length}`}
function point(e){const r=canvas.getBoundingClientRect();return [Math.max(0,Math.min(image.naturalWidth,(e.clientX-r.left)*image.naturalWidth/r.width)),Math.max(0,Math.min(image.naturalHeight,(e.clientY-r.top)*image.naturalHeight/r.height))]}
canvas.onmousedown=e=>start=point(e);canvas.onmouseup=e=>{if(!start)return;const end=point(e),box=[Math.min(start[0],end[0]),Math.min(start[1],end[1]),Math.max(start[0],end[0]),Math.max(start[1],end[1])];start=null;if(box[2]-box[0]<2||box[3]-box[1]<2)return;current().boxes??=[];current().boxes.push({class_name:document.getElementById('class').value,xyxy:box});dirty();draw()};
function move(d){document.getElementById('index').value=Number(document.getElementById('index').value)+d;show()}
function useSuggestions(){if((current().boxes||[]).length&&!confirm('Thay các bbox đang có bằng gợi ý?'))return;current().boxes=(suggestions[current().sample_id]||[]).map(b=>({class_name:b.class_name,xyxy:[...b.xyxy]}));dirty();draw()}
function removeBox(){if(selected<0)return;current().boxes.splice(selected,1);selected=-1;dirty();draw()}
function clearBoxes(){if(!confirm('Xóa mọi bbox ảnh này? Không có bbox không có nghĩa là negative đã duyệt.'))return;current().boxes=[];dirty();draw()}
function validateBoxes(s){if(!Array.isArray(s.boxes))throw Error('Cần kiểm tra/nạp/vẽ bbox; null chưa phải negative');const [w,h]=s.original_wh,seen=new Set();for(const b of s.boxes){const v=b.xyxy;if(!['ball','human','rim'].includes(b.class_name)||!Array.isArray(v)||v.length!==4||v.some(x=>!Number.isFinite(x))||!(0<=v[0]&&v[0]<v[2]&&v[2]<=w&&0<=v[1]&&v[1]<v[3]&&v[3]<=h))throw Error('BBox/class không hợp lệ');const key=b.class_name+JSON.stringify(v);if(seen.has(key))throw Error('BBox trùng hoàn toàn');seen.add(key)}if(s.ball_visibility==='visible'&&!s.boxes.some(b=>b.class_name==='ball'))throw Error('Bóng visible cần bbox ball');if(s.ball_visibility==='not_visible'&&s.boxes.some(b=>b.class_name==='ball'))throw Error('Cần đối soát ball visibility với bbox');if(['unreviewed','uncertain'].includes(s.ball_visibility)||s.scene_status==='unreviewed')throw Error('Cần chốt scene/visibility hoặc bỏ qua ảnh')}
function approveImage(){try{if(!document.getElementById('checked').checked)throw Error('Cần xác nhận đã đối soát toàn ảnh');const s=current();s.scene_status=document.getElementById('scene').value;s.ball_visibility=document.getElementById('visibility').value;validateBoxes(s);s.review_status='approved';draw()}catch(e){alert(e.message)}}
function skipImage(){const reason=prompt('Lý do bỏ qua (không rõ nhãn, duplicate, ngoài scope…):');if(!reason?.trim())return;current().review_status='skipped';current().skip_reason=reason.trim();draw()}
function applyEditor(){try{const x=JSON.parse(editor.value);if(x.source_sha256!==data.source_sha256||x.samples.length!==data.samples.length||x.samples.some((s,i)=>s.image_sha256!==data.samples[i].image_sha256))throw Error('Sai source/frame packet');data=x;show()}catch(e){alert(e.message)}}
function loadFile(e){const f=e.target.files[0];if(!f)return;const reader=new FileReader();reader.onload=()=>{editor.value=reader.result;applyEditor()};reader.readAsText(f)}
function download(approved){try{const x=structuredClone(data);x.review_status='draft';x.training_ready=false;if(approved){const r=document.getElementById('reviewer').value.trim();if(!r)throw Error('Cần reviewer');if(x.samples.some(s=>!['approved','skipped'].includes(s.review_status)))throw Error('Còn ảnh chưa review; xuất draft để lưu tiến độ');for(const s of x.samples)if(s.review_status==='approved')validateBoxes(s);if(!x.samples.some(s=>s.review_status==='approved'))throw Error('Chưa có ảnh nào được duyệt');x.review_status='approved';x.reviewer=r;x.reviewed_utc=new Date().toISOString()}const url=URL.createObjectURL(new Blob([JSON.stringify(x,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=(approved?'reviewed-':'draft-')+'task07a-pilot.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){alert(e.message)}}
show();
</script>'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pilot-dir',required=True);p.add_argument('--output-dir',required=True);args=p.parse_args()
    pilot=Path(args.pilot_dir).resolve();packet=json.loads((pilot/'annotations-draft.json').read_text(encoding='utf-8'))
    run=json.loads((pilot/'run.json').read_text());assert run['status']=='completed' and not run['training_ready']
    out=new_output(args.output_dir,[pilot]);write_json(out/'run.json',dict(status='running',source_sha256=run['source_sha256'],model_loaded=False))
    snapshot=out/'source-snapshot';snapshot.mkdir()
    sources=[Path(__file__),*(ROOT/'src/basketball_scoreboard').glob('*.py')]
    for source in sources:
        dest=snapshot/source.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    detector=TiledBallDetector(ModelConfig(confidence_threshold=.15,max_edge=1920),grid=2,overlap=.2,
        excluded_boxes=[[.02,.73,.27,1.]],onnx_threads=4);detector.warmup()
    runtime=detector.get_runtime_info();suggestions={};started=time.perf_counter()
    with (out/'suggestions.jsonl').open('x',encoding='utf-8') as handle:
        for index,sample in enumerate(packet['samples']):
            path=(pilot/sample['image']).resolve()
            if not path.is_relative_to(pilot) or file_hash(path)!=sample['image_sha256']:raise ValueError('Source sample differs')
            image=cv2.imread(str(path));records,ms=detector.detect(image)
            boxes=[dict(class_name=r.class_name,xyxy=r.xyxy,confidence=r.confidence) for r in records]
            suggestions[sample['sample_id']]=boxes
            handle.write(json.dumps(dict(sample_id=sample['sample_id'],image_sha256=sample['image_sha256'],model_call_ms=ms,boxes=boxes,review_status='model_suggestion_not_GT'))+'\n');handle.flush()
            if index%10==0:
                write_json(out/'progress.json',dict(status='running',samples=index+1,total=len(packet['samples'])))
                print('Suggested',index+1,'/',len(packet['samples']),flush=True)
    safe=lambda x:json.dumps(x,ensure_ascii=False).replace('</','<\\/')
    (out/'review.html').write_text(PAGE.replace('PACKET_JSON',safe(packet)).replace('SUGGESTIONS_JSON',safe(suggestions)),encoding='utf-8')
    summary=dict(status='completed',source_sha256=run['source_sha256'],pilot_packet_sha256=file_hash(pilot/'annotations-draft.json'),
        runtime=runtime,samples=len(suggestions),wall_s=time.perf_counter()-started,training_labels_exported=False,training_started=False,
        scope='Model-assisted suggestions only; every kept image needs source review',script_sha256=file_hash(__file__))
    write_json(out/'run.json',summary);write_json(out/'progress.json',dict(status='completed',samples=len(suggestions)))
    print('Completed local draft suggestions',len(suggestions));return 0


if __name__=='__main__':
    try:sys.exit(main())
    except Exception as error:print('Pilot suggestions failed ('+type(error).__name__+')',file=sys.stderr);sys.exit(1)
