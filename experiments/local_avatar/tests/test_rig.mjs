import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';
import {AvatarRig,deformJaw,headPositions,landmarks,lipMesh,meshNormals,mouthShape,rotatePoint,surfaceMesh} from '../web/rig.mjs';
const schema=JSON.parse(readFileSync(new URL('../web/rig-schema.json',import.meta.url)));
const rig=new AvatarRig(schema);

test('pose export preserves exact order and rejects incompatible labels',()=>{
  const original=rig.preset('rounded'),record=rig.export(original,'preset:rounded');
  assert.deepEqual(rig.import(record),original);
  assert.equal(record.vector.length,12);
  assert.throws(()=>rig.import({...record,control_order:[...record.control_order].reverse()}));
  assert.throws(()=>rig.import({...record,schema_version:2}));
  assert.throws(()=>rig.import({...record,pose:{...record.pose,jawOpen:.99}}));
});
test('invalid controls cannot become silent training labels',()=>{
  for(const bad of [{jawOpen:NaN},{headYaw:Infinity},{smile:true},{jawOpen:null},{jawOpen:2},{missing:0}]) assert.throws(()=>rig.normalize(bad));
  assert.throws(()=>rig.fromVector([0]));
  assert.equal(rig.normalize({jawOpen:2},{clamp:true}).jawOpen,1);
});
test('lip closure seals aperture while preserving jaw movement',()=>{
  const open=rig.normalize({jawOpen:1}),closed=rig.normalize({jawOpen:1,lipClosure:1});
  assert.ok(mouthShape(open).halfHeight>.16);
  assert.equal(mouthShape(closed).halfHeight,.003);
  assert.equal(mouthShape(open).jawRadians,mouthShape(closed).jawRadians);
  assert.notDeepEqual(deformJaw([0,-1.1,.15],closed),deformJaw([0,-1.1,.15],rig.neutral));
});
test('rounding and spreading remain distinguishable at the same jaw opening',()=>{
  const round=mouthShape(rig.normalize({jawOpen:.4,lipRound:1}));
  const spread=mouthShape(rig.normalize({jawOpen:.4,lipSpread:1}));
  assert.ok(round.width<spread.width);
  assert.ok(round.frontZ>spread.frontZ);
});
test('coordinate signs and rotations preserve length',()=>{
  const yaw=rotatePoint([0,0,1],rig.normalize({headYaw:.1}));assert.ok(yaw[0]>0);
  const pitch=rotatePoint([0,0,1],rig.normalize({headPitch:.1}));assert.ok(pitch[1]<0);
  const roll=rotatePoint([0,1,0],rig.normalize({headRoll:.1}));assert.ok(roll[0]<0);
  assert.ok(Math.abs(Math.hypot(...rotatePoint([1,2,3],rig.preset('turned')))-Math.sqrt(14))<1e-12);
});
test('jaw leaves upper face stable while moving the chin',()=>{
  const pose=rig.normalize({jawOpen:1});
  assert.deepEqual(deformJaw([0,.6,.6],pose),[0,.6,.6]);
  assert.ok(deformJaw([0,-1.1,.15],pose)[1]<-1.1);
});
test('all presets produce finite bounded mesh data and outward normals',()=>{
  const surface=surfaceMesh();
  const neutralPositions=headPositions(surface,rig.neutral),neutralNormals=meshNormals(neutralPositions,surface.indices);
  for(let i=0;i<neutralPositions.length;i+=3){
    const radial=[neutralPositions[i],neutralPositions[i+1]-.1,neutralPositions[i+2]];
    assert.ok(radial.reduce((sum,value,axis)=>sum+value*neutralNormals[i+axis],0)>0,'neutral normals must face away from head center');
  }
  for(const preset of schema.presets) {
    const pose=rig.preset(preset.id),positions=headPositions(surface,pose),normals=meshNormals(positions,surface.indices),lips=lipMesh(pose);
    assert.equal(positions.length,surface.positions.length);
    assert.ok([...positions,...normals,...lips.positions].every(Number.isFinite));
    assert.ok([...lips.indices].every(index=>index<lips.positions.length/3));
    assert.ok(Object.values(landmarks(pose)).flat().every(Number.isFinite));
    for(let i=0;i<normals.length;i+=3) assert.ok(Math.abs(Math.hypot(...normals.slice(i,i+3))-1)<1e-5);
  }
});
