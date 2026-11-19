const assert = require('node:assert/strict');
const {frameAt} = require('../src/basketball_scoreboard/spatial_playback.js');
const person = {id:'T1',player_id:'P1',team_id:'A',role:'player',segment:0,source_scope:['run','video','hash','cam'],xy:[0,5],continuity_start_s:0};
const frames = [{time:0,players:[person]},{time:.2,players:[{...person,xy:[1,5]}]}];
assert.deepEqual(frameAt(frames,.1).players[0].xy,[.5,5]);
assert.deepEqual(frames[0].players[0].xy,[0,5]);
for (const change of [{player_id:'other'},{team_id:'other'},{role:'referee'},{segment:1},{source_scope:['cam2']},{continuity_start_s:.15},{xy:null}]) {
  const broken=[frames[0],{time:.2,players:[{...person,xy:[1,5],...change}]}];
  assert.deepEqual(frameAt(broken,.1).players[0].xy,[0,5]);
}
assert.equal(frameAt(frames,.1,[{start_s:.05,end_s:.15}]),null);
assert.equal(frameAt(frames,-.1),null);
assert.equal(frameAt(frames,1),null);
const future=[frames[0],{time:.2,players:[{...person,id:'new',xy:[1,5]}]}];
assert.equal(frameAt(future,.1).players.length,1);
assert.equal(frameAt(future,.1).players[0].id,'T1');
console.log('Spatial playback regressions passed: interpolation, identity, camera, visibility, exclusions and source immutability.');
