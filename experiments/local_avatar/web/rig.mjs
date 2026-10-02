// Authored face representation. Pure geometry and validation; no DOM or pretrained assets.
export class AvatarRig {
  constructor(schema) {
    if (schema.schema_id !== 'local-avatar-head-controls' || schema.schema_version !== 1 || schema.controls.length !== 12) {
      throw new Error('Unsupported rig schema');
    }
    this.schema = schema;
    this.controls = schema.controls;
    this.names = this.controls.map(item => item.name);
    if (new Set(this.names).size !== 12) throw new Error('Duplicate control names');
    this.neutral = Object.fromEntries(this.controls.map(item => [item.name, item.neutral]));
    this.normalize(this.neutral);
  }
  normalize(pose, {clamp = false} = {}) {
    if (!pose || typeof pose !== 'object' || Array.isArray(pose)) throw new Error('A pose must be a named object');
    if (Object.keys(pose).some(key => !this.names.includes(key))) throw new Error('Unknown control');
    return Object.fromEntries(this.controls.map(control => {
      let value = Object.hasOwn(pose,control.name) ? pose[control.name] : control.neutral;
      if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error('Controls must be finite numbers');
      if (value < control.min || value > control.max) {
        if (!clamp) throw new Error(`Out of range: ${control.name}`);
        value = Math.max(control.min, Math.min(control.max, value));
      }
      return [control.name, value];
    }));
  }
  vector(pose) { const normalized = this.normalize(pose); return this.names.map(name => normalized[name]); }
  fromVector(vector) {
    if (!Array.isArray(vector) || vector.length !== 12) throw new Error('Expected twelve ordered controls');
    return this.normalize(Object.fromEntries(this.names.map((name, index) => [name, vector[index]])));
  }
  export(pose, source = 'manual') {
    const normalized = this.normalize(pose);
    return {schema_id: this.schema.schema_id, schema_version: 1, asset_id: this.schema.asset_id,
      control_order: this.names, source, pose: normalized, vector: this.vector(normalized)};
  }
  import(record) {
    if (record.schema_id !== this.schema.schema_id || record.schema_version !== 1 || record.asset_id !== this.schema.asset_id ||
        JSON.stringify(record.control_order) !== JSON.stringify(this.names)) throw new Error('Pose schema or control order mismatch');
    const pose = this.fromVector(record.vector);
    if (JSON.stringify(this.vector(record.pose)) !== JSON.stringify(record.vector)) throw new Error('Named pose differs from vector');
    return pose;
  }
  preset(id) {
    const item = this.schema.presets.find(preset => preset.id === id);
    if (!item) throw new Error('Unknown pose preset');
    return this.normalize(item.pose);
  }
}

export function mouthShape(pose) {
  const seal = 1-pose.lipClosure;
  const top = (.17*pose.jawOpen+.07*pose.upperLipRaise)*seal;
  const bottom = (.17*pose.jawOpen+.07*pose.lowerLipDepress)*seal;
  return {width:.30*(1+.45*pose.lipSpread-.38*pose.lipRound)+.04*pose.smile,
    halfHeight:.003+(top+bottom)/2, centerY:-.40-.06*pose.jawOpen+(top-bottom)/2,
    cornerLift:.065*pose.smile, frontZ:.716+.10*pose.lipRound, jawRadians:.28*pose.jawOpen};
}

export function rotatePoint([x,y,z], pose) {
  const cy=Math.cos(pose.headYaw), sy=Math.sin(pose.headYaw);
  const cx=Math.cos(pose.headPitch), sx=Math.sin(pose.headPitch);
  const cz=Math.cos(pose.headRoll), sz=Math.sin(pose.headRoll);
  const a=cy*x+sy*z, b=y, c=-sy*x+cy*z;
  const d=a, e=cx*b-sx*c, f=sx*b+cx*c;
  return [cz*d-sz*e, sz*d+cz*e, f];
}
export function rotationMatrix(pose) {
  return new Float32Array([[1,0,0],[0,1,0],[0,0,1]].flatMap(vector => rotatePoint(vector,pose)));
}

function clamp01(value) { return Math.max(0,Math.min(1,value)); }
export function deformJaw([x,y,z], pose) {
  const weight=clamp01((-.15-y)/.85), angle=.28*pose.jawOpen*weight;
  const dy=y+.15, dz=z+.10;
  return [x, Math.cos(angle)*dy-Math.sin(angle)*dz-.15, Math.sin(angle)*dy+Math.cos(angle)*dz-.10];
}
export function surfaceMesh(rows=32, columns=48) {
  const positions=[], normals=[], indices=[];
  for (let row=0;row<=rows;row++) for(let column=0;column<=columns;column++) {
    const t=Math.PI*row/rows, p=2*Math.PI*column/columns;
    const vector=[Math.sin(t)*Math.cos(p),Math.cos(t),Math.sin(t)*Math.sin(p)];
    positions.push(...vector); normals.push(...vector);
  }
  for(let row=0;row<rows;row++) for(let column=0;column<columns;column++) {
    const a=row*(columns+1)+column,b=a+columns+1;
    indices.push(a,a+1,b,b,a+1,b+1);
  }
  return {positions:new Float32Array(positions),normals:new Float32Array(normals),indices:new Uint16Array(indices)};
}
export function headPositions(surface,pose) {
  const output=new Float32Array(surface.positions.length);
  for(let i=0;i<output.length;i+=3) {
    output.set(deformJaw([surface.positions[i]*.88,surface.positions[i+1]*1.25+.1,surface.positions[i+2]*.72],pose),i);
  }
  return output;
}
export function meshNormals(positions,indices) {
  const normals=new Float32Array(positions.length);
  for(let i=0;i<indices.length;i+=3) {
    const a=indices[i]*3,b=indices[i+1]*3,c=indices[i+2]*3;
    const u=[positions[b]-positions[a],positions[b+1]-positions[a+1],positions[b+2]-positions[a+2]];
    const v=[positions[c]-positions[a],positions[c+1]-positions[a+1],positions[c+2]-positions[a+2]];
    const n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
    for(const offset of [a,b,c]) for(let j=0;j<3;j++) normals[offset+j]+=n[j];
  }
  for(let i=0;i<normals.length;i+=3) {
    const length=Math.hypot(normals[i],normals[i+1],normals[i+2]);
    if(length<1e-8) { normals[i+1]=positions[i+1]>=.1?1:-1; }
    else for(let j=0;j<3;j++) normals[i+j]/=length;
  }
  return normals;
}
export function lipMesh(pose,segments=64) {
  const shape=mouthShape(pose),positions=[],normals=[],indices=[];
  for(let i=0;i<=segments;i++) {
    const angle=i/segments*2*Math.PI, x=Math.cos(angle), y=Math.sin(angle);
    for(const outer of [0,1]) {
      positions.push(x*(shape.width+outer*.037),shape.centerY+shape.cornerLift*x*x+y*(shape.halfHeight+outer*.033),
        shape.frontZ+outer*.005+.008*Math.abs(y));
      normals.push(0,0,1);
    }
    if(i<segments) { const a=2*i;indices.push(a,a+1,a+2,a+1,a+3,a+2); }
  }
  return {positions:new Float32Array(positions),normals:new Float32Array(normals),indices:new Uint16Array(indices)};
}
export function landmarks(pose) {
  const shape=mouthShape(pose);
  return {
    mouthLeft:[-shape.width,shape.centerY+shape.cornerLift,shape.frontZ],
    mouthRight:[shape.width,shape.centerY+shape.cornerLift,shape.frontZ],
    upperLip:[0,shape.centerY+shape.halfHeight,shape.frontZ],
    lowerLip:[0,shape.centerY-shape.halfHeight,shape.frontZ],
    chin:deformJaw([0,-1.10,.15],pose),eyeLeft:[.31,.4,.75],eyeRight:[-.31,.4,.75],nose:[0,.03,.90],
  };
}
