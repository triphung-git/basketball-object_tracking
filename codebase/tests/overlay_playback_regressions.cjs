const assert = require('node:assert/strict');
const {boxesAt, frameSync} = require('../src/basketball_scoreboard/overlay_playback.js');
const first = {id:'t', box:[0,0,10,10], segment_id:'s', continuity_start_s:0, role:'unknown'};
const next = {...first, box:[10,0,20,10]};
let frames = [{time:0,boxes:[first]}, {time:.2,boxes:[next,{...next,id:'new'}]}];
assert.deepEqual(boxesAt(frames,.15).map(p=>p.id), ['t']); // no future birth
assert.equal(boxesAt(frames,.1)[0].box[0],5);
frames[1].boxes[0] = {...next, player_id:'future_player'};
assert.equal(boxesAt(frames,.1)[0].player_id,undefined);
assert.equal(boxesAt(frames,.1)[0].box[0],0);
frames[1].boxes[0] = {...next, segment_id:'another_scene'};
assert.equal(boxesAt(frames,.1)[0].box[0],0);
frames[1].boxes[0] = {...next, continuity_start_s:.15};
assert.equal(boxesAt(frames,.1)[0].box[0],0); // intervening occlusion
assert.deepEqual(boxesAt(frames,1),[]);
for (const native of [false,true]) {
  let n=0,queue=new Map(),rendered=[];
  const schedule = cb => {const id=n++;queue.set(id,cb);return id;};
  const cancel = id => queue.delete(id);
  const animation = {requestAnimationFrame:schedule,cancelAnimationFrame:cancel};
  const video = {paused:false,ended:false,currentTime:.8};
  if(native) Object.assign(video,{requestVideoFrameCallback:schedule,cancelVideoFrameCallback:cancel});
  const sync=frameSync(video,t=>rendered.push(t),animation);
  sync.start();sync.start();sync.start();
  assert.equal(queue.size,1); // id=0 is valid and must not spawn duplicate loops
  const [id,cb]=[...queue][0];queue.delete(id);cb(0,{mediaTime:.1});
  assert.equal(rendered[0],.1);
  assert.equal(queue.size,1);
  sync.stop();assert.equal(queue.size,0);
  video.paused=true;sync.start();assert.equal(queue.size,0);
}
console.log('Overlay temporal and frame-loop regressions passed');
