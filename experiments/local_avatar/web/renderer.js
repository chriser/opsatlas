import {AvatarRig,headPositions,landmarks,lipMesh,meshNormals,mouthShape,rotationMatrix,surfaceMesh} from './rig.mjs';
const canvas=document.querySelector('#head'),status=document.querySelector('#renderer-status');
const runStatus=document.querySelector('#run-status'),buttons=['short-run','long-run'].map(id=>document.getElementById(id));
const response=await fetch('/rig-schema.json');
if(!response.ok)throw new Error('Rig schema unavailable');
const rig=new AvatarRig(await response.json());
let pose=rig.normalize({}),source='preset:neutral',animate=false,run=null,nextFrame=0,contextLost=false;
const samples=[],controls=document.querySelector('#controls');
for(const control of rig.controls){
 const label=document.createElement('label'),name=document.createElement('span'),value=document.createElement('output');
 name.textContent=control.label;value.id=`value-${control.name}`;label.append(name,value);
 const input=document.createElement('input'),degrees=control.unit==='radians';
 input.id=control.name;input.type='range';input.min=degrees?-10:control.min;input.max=degrees?10:control.max;input.step=degrees?.5:.01;
 input.setAttribute('aria-label',control.label);input.title=control.meaning;
 input.addEventListener('input',()=>{stopPreview();pose[control.name]=Number(input.value)*(degrees?Math.PI/180:1);pose=rig.normalize(pose,{clamp:true});source='manual';syncControls();});
 label.append(input);controls.append(label);
}
for(const preset of rig.schema.presets){const button=document.createElement('button');button.textContent=preset.label;
 button.onclick=()=>{stopPreview();pose=rig.preset(preset.id);source=`preset:${preset.id}`;syncControls();};document.querySelector('#presets').append(button);}
function stopPreview(){animate=false;document.querySelector('#animate').textContent='Preview pose sequence';if(source==='preview'){source='manual';syncControls();}}
function syncControls(){
 for(const control of rig.controls){const degrees=control.unit==='radians',value=pose[control.name]*(degrees?180/Math.PI:1);
  document.getElementById(control.name).value=value;document.getElementById(`value-${control.name}`).textContent=degrees?`${value.toFixed(1)}°`:value.toFixed(2);}
 document.querySelector('#pose-name').textContent=source.startsWith('preset:')?rig.schema.presets.find(p=>p.id===source.slice(7)).label:source==='preview'?'Preview pose sequence':'Custom pose';
 document.querySelector('#pose-vector').textContent=JSON.stringify(rig.export(pose,source),null,2);
 document.querySelector('#pose-save-status').textContent='';
}
syncControls();
document.querySelector('#export-pose').onclick=async()=>{stopPreview();const message=document.querySelector('#pose-save-status');
 try{const result=await fetch('/pose',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(rig.export(pose,source))});
  if(!result.ok)throw new Error('Pose save failed');message.textContent='Pose saved locally as avatar-rig-pose-v1.json in the lab runtime folder. Saving again replaces this file.';
 }catch(error){message.textContent=error.message;}};
const gl=canvas.getContext('webgl',{antialias:true});
function shader(type,code){const item=gl.createShader(type);gl.shaderSource(item,code);gl.compileShader(item);if(!gl.getShaderParameter(item,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(item));return item;}
function percentile(values,p){const ordered=[...values].sort((a,b)=>a-b);return ordered[Math.max(0,Math.ceil(p*ordered.length)-1)]||0;}
if(!gl){status.textContent='WebGL unavailable. Pose inspection and export still work.';buttons.forEach(b=>b.disabled=true);}
else{
 const program=gl.createProgram();
 gl.attachShader(program,shader(gl.VERTEX_SHADER,`
 attribute vec3 position;attribute vec3 normal;uniform vec3 offset;uniform vec3 scale;uniform mat3 rotation;uniform float aspect;
 varying float light;varying vec3 localPoint;
 void main(){localPoint=position*scale+offset;vec3 p=rotation*localPoint;vec3 n=normalize(rotation*(normal/scale));
 light=.35+.65*max(0.,dot(n,normalize(vec3(-.5,.8,1.))));gl_Position=vec4(p.x/(2.1*aspect),p.y/2.1,-p.z/5.,1.);gl_PointSize=6.;}`));
 gl.attachShader(program,shader(gl.FRAGMENT_SHADER,`
 precision mediump float;varying float light;varying vec3 localPoint;uniform vec3 color;uniform float headSurface;uniform vec4 aperture;
 void main(){float nx=localPoint.x/aperture.x;float ny=(localPoint.y-aperture.z-aperture.w*nx*nx)/aperture.y;
 if(headSurface>.5&&localPoint.z>.3&&nx*nx+ny*ny<1.)discard;gl_FragColor=vec4(color*light,1.);}`));
 gl.linkProgram(program);if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program));gl.useProgram(program);
 const uniform=Object.fromEntries(['offset','scale','rotation','aspect','color','headSurface','aperture'].map(name=>[name,gl.getUniformLocation(program,name)]));
 const attributes=['position','normal'].map(name=>gl.getAttribLocation(program,name));
 function upload(mesh,dynamic=false){const gpu={count:mesh.indices.length,buffers:[],index:gl.createBuffer()};
  for(const data of[mesh.positions,mesh.normals]){const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,data,dynamic?gl.DYNAMIC_DRAW:gl.STATIC_DRAW);gpu.buffers.push(b);}
  gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,gpu.index);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,mesh.indices,gl.STATIC_DRAW);return gpu;}
 function update(gpu,mesh){for(let i=0;i<2;i++){gl.bindBuffer(gl.ARRAY_BUFFER,gpu.buffers[i]);gl.bufferSubData(gl.ARRAY_BUFFER,0,i?mesh.normals:mesh.positions);}}
 function bind(gpu){gpu.buffers.forEach((b,i)=>{gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.enableVertexAttribArray(attributes[i]);gl.vertexAttribPointer(attributes[i],3,gl.FLOAT,false,0,0);});gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,gpu.index);}
 const surface=surfaceMesh(),sphereGpu=upload(surface),initial=headPositions(surface,pose);
 const headGpu=upload({positions:initial,normals:meshNormals(initial,surface.indices),indices:surface.indices},true);
 const lipsGpu=upload(lipMesh(pose),true),guideGpu=upload({positions:new Float32Array(24),normals:new Float32Array(24).fill(1),indices:new Uint16Array(0)},true);
 const identity=new Float32Array([1,0,0,0,1,0,0,0,1]);let lastJaw=-1,lastMouth='';
 gl.enable(gl.DEPTH_TEST);gl.clearColor(.055,.094,.13,1);gl.viewport(0,0,1280,720);gl.uniform1f(uniform.aspect,1280/720);
 function part(gpu,offset,scale,color,rotation,head=false){bind(gpu);gl.uniform3fv(uniform.offset,offset);gl.uniform3fv(uniform.scale,scale);gl.uniform3fv(uniform.color,color);
  gl.uniformMatrix3fv(uniform.rotation,false,rotation);gl.uniform1f(uniform.headSurface,head?1:0);gl.drawElements(gl.TRIANGLES,gpu.count,gl.UNSIGNED_SHORT,0);}
 function draw(current){const shape=mouthShape(current),rotation=rotationMatrix(current),key=JSON.stringify(shape);
  if(lastJaw!==current.jawOpen){const positions=headPositions(surface,current);update(headGpu,{positions,normals:meshNormals(positions,surface.indices)});lastJaw=current.jawOpen;}
  if(lastMouth!==key){update(lipsGpu,lipMesh(current));lastMouth=key;}
  gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.uniform4fv(uniform.aperture,[shape.width,shape.halfHeight,shape.centerY,shape.cornerLift]);
  part(sphereGpu,[0,-1.7,-.2],[1.35,.55,.6],[.17,.29,.36],identity);part(sphereGpu,[0,-1.05,0],[.4,.5,.38],[.68,.45,.32],identity);
  part(headGpu,[0,0,0],[1,1,1],[.78,.55,.39],rotation,true);
  part(sphereGpu,[0,shape.centerY,.36],[shape.width+.07,shape.halfHeight+.06,.2],[.12,.035,.025],rotation);
  if(shape.halfHeight>.02){part(sphereGpu,[0,shape.centerY+shape.halfHeight*.66,.555],[shape.width*.78,.03,.025],[.91,.88,.76],rotation);
   part(sphereGpu,[0,shape.centerY-shape.halfHeight*.6,.54],[shape.width*.62,.027,.025],[.56,.22,.20],rotation);}
  part(lipsGpu,[0,0,0],[1,1,1],[.59,.32,.25],rotation);
  for(const x of[-.89,.89])part(sphereGpu,[x,.15,0],[.16,.29,.15],[.68,.45,.32],rotation);
  for(const[x,blinkName]of[[-.31,'blinkRight'],[.31,'blinkLeft']]){const openness=1-current[blinkName];
   if(openness>.01){part(sphereGpu,[x,.4,.66],[.2,.12*openness,.075],[.94,.94,.87],rotation);part(sphereGpu,[x,.4,.735],[.065,.072*openness,.028],[.15,.31,.33],rotation);}
   else part(sphereGpu,[x,.4,.70],[.2,.012,.03],[.39,.24,.18],rotation);
   part(sphereGpu,[x,.61,.6],[.22,.034,.05],[.22,.16,.13],rotation);}
  part(sphereGpu,[0,.03,.71],[.12,.26,.18],[.75,.51,.35],rotation);
  if(document.querySelector('#guides').checked){update(guideGpu,{positions:new Float32Array(Object.values(landmarks(current)).flat()),normals:new Float32Array(24).fill(1)});bind(guideGpu);
   gl.uniform3fv(uniform.offset,[0,0,0]);gl.uniform3fv(uniform.scale,[1,1,1]);gl.uniform3fv(uniform.color,[.45,1,.83]);gl.uniformMatrix3fv(uniform.rotation,false,rotation);gl.uniform1f(uniform.headSurface,0);
   gl.disable(gl.DEPTH_TEST);gl.drawArrays(gl.POINTS,0,8);gl.enable(gl.DEPTH_TEST);}
  gl.finish();
 }
 let previewStart=0;
 document.querySelector('#animate').onclick=event=>{if(animate){stopPreview();return;}animate=true;previewStart=performance.now();event.target.textContent='Stop preview';};
 function preview(now){const phase=(now-previewStart)/1800,index=Math.floor(phase)%rig.schema.presets.length,next=(index+1)%rig.schema.presets.length;
  const a=rig.preset(rig.schema.presets[index].id),b=rig.preset(rig.schema.presets[next].id),raw=phase-Math.floor(phase),weight=raw<.5?0:(raw-.5)*2,t=weight*weight*(3-2*weight);
  return Object.fromEntries(rig.names.map(name=>[name,a[name]+(b[name]-a[name])*t]));}
 canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();contextLost=true;run=null;buttons.forEach(b=>b.disabled=true);status.textContent='Renderer context lost. Reload to retry.';runStatus.textContent='Any active measurement was discarded.';});
 document.addEventListener('visibilitychange',()=>{if(run&&document.hidden)run.hidden++;});
 async function finishRun(now){const completed=run;run=null;
  const result={schema_version:1,duration_ms:now-completed.start,frames:completed.draws.length,target_fps:30,visibility_interruptions:completed.hidden,
   interval_p50_ms:percentile(completed.intervals,.5),interval_p95_ms:percentile(completed.intervals,.95),draw_p95_ms:percentile(completed.draws,.95),
   estimated_missed_frames:completed.missed,width:1280,height:720,webgl_errors:completed.errors,started_at_unix_ms:performance.timeOrigin+completed.start,finished_at_unix_ms:performance.timeOrigin+now};
  document.querySelector('#renderer-report').textContent=JSON.stringify(result,null,2);
  try{const saved=await fetch('/renderer-benchmark',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(result)});
   if(!saved.ok)throw new Error('Report save failed');runStatus.textContent=completed.hidden?'Saved with a visibility interruption. Repeat in a visible tab.':'Measurement saved locally. Frame gaps include browser scheduling.';
  }catch(error){runStatus.textContent=error.message;}buttons.forEach(b=>b.disabled=false);
 }
 function frame(now){if(!contextLost&&now+1>=nextFrame){const start=performance.now();if(animate){pose=preview(now);source='preview';syncControls();}draw(pose);const elapsed=performance.now()-start;
  samples.push(elapsed);if(samples.length>120)samples.shift();
  if(run){run.draws.push(elapsed);if(run.last!==null){const delta=now-run.last;run.intervals.push(delta);run.missed+=Math.max(0,Math.round(delta/(1000/30))-1);}
   run.last=now;if(gl.getError()!==gl.NO_ERROR)run.errors++;
   runStatus.textContent=`Measuring ${Math.min(run.duration/1000,(now-run.start)/1000).toFixed(1)} / ${run.duration/1000} seconds. Keep this tab visible.`;
   if(now-run.start>=run.duration)void finishRun(now);}
  nextFrame=now+1000/30;status.textContent=`1280 × 720 · target 30 fps · draw p95 ${percentile(samples,.95).toFixed(2)} ms`;}
  requestAnimationFrame(frame);}
 function startRun(seconds){if(run||contextLost)return;run={start:performance.now(),duration:seconds*1000,draws:[],intervals:[],last:null,missed:0,hidden:document.hidden?1:0,errors:0};buttons.forEach(b=>b.disabled=true);}
 buttons[0].onclick=()=>startRun(30);buttons[1].onclick=()=>startRun(600);requestAnimationFrame(frame);
}
try{const result=await fetch('/device-benchmark.json');if(result.ok){const report=await result.json();document.querySelector('#device-report').textContent=report.results.map(item=>`${item.device.toUpperCase()}: ${item.parameters.toLocaleString()} parameters\nInference p95: ${item.warm_inference.p95_ms.toFixed(2)} ms\nTraining step p95: ${item.training_step.p95_ms.toFixed(2)} ms`).join('\n\n');}}
catch{document.querySelector('#device-report').textContent='No device report available.';}
