const canvas = document.querySelector('#head');
const gl = canvas.getContext('webgl', {antialias: true, preserveDrawingBuffer: false});
const status = document.querySelector('#renderer-status');
const runStatus = document.querySelector('#run-status');
const buttons = ['short-run', 'long-run'].map(id => document.getElementById(id));
let animate = false, run = null, nextFrame = 0, contextLost = false;
const samples = [];
function shader(type, source) {
  const item = gl.createShader(type); gl.shaderSource(item, source); gl.compileShader(item);
  if (!gl.getShaderParameter(item, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(item));
  return item;
}
if (!gl) { status.textContent = 'WebGL unavailable. Device checks can still run.'; buttons.forEach(b => b.disabled = true); }
else {
  const program = gl.createProgram();
  gl.attachShader(program, shader(gl.VERTEX_SHADER, `
    attribute vec3 position; attribute vec3 normal;
    uniform vec3 offset; uniform vec3 scale; uniform float yaw; uniform float aspect;
    varying float light;
    void main(){
      mat3 r=mat3(cos(yaw),0.,-sin(yaw),0.,1.,0.,sin(yaw),0.,cos(yaw));
      vec3 p=r*(position*scale+offset); vec3 n=normalize(r*(normal/scale));
      light=.35+.65*max(0.,dot(n,normalize(vec3(-.5,.8,1.))));
      gl_Position=vec4(p.x/(2.1*aspect),p.y/2.1,-p.z/5.,1.);
    }`));
  gl.attachShader(program, shader(gl.FRAGMENT_SHADER, `precision mediump float; varying float light; uniform vec3 color; void main(){gl_FragColor=vec4(color*light,1.);}`));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(program));
  gl.useProgram(program);
  const positions = [], normals = [], indices = [], rows = 32, columns = 48;
  for (let row = 0; row <= rows; row++) for (let column = 0; column <= columns; column++) {
    const t = Math.PI * row / rows, p = 2 * Math.PI * column / columns;
    const v = [Math.sin(t)*Math.cos(p), Math.cos(t), Math.sin(t)*Math.sin(p)];
    positions.push(...v); normals.push(...v);
  }
  for (let row = 0; row < rows; row++) for (let col = 0; col < columns; col++) {
    const a = row*(columns+1)+col, b = a+columns+1; indices.push(a,b,a+1,b,b+1,a+1);
  }
  for (const [name, data] of [['position', positions], ['normal', normals]]) {
    const buffer = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(data), gl.STATIC_DRAW);
    const attribute = gl.getAttribLocation(program, name); gl.enableVertexAttribArray(attribute); gl.vertexAttribPointer(attribute,3,gl.FLOAT,false,0,0);
  }
  const buffer = gl.createBuffer(); gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, buffer); gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array(indices),gl.STATIC_DRAW);
  const uniforms = Object.fromEntries(['offset','scale','color','yaw','aspect'].map(name => [name, gl.getUniformLocation(program,name)]));
  gl.enable(gl.DEPTH_TEST); gl.clearColor(.055,.094,.13,1); gl.viewport(0,0,1280,720); gl.uniform1f(uniforms.aspect,1280/720);
  function sphere(offset, scale, color) {
    gl.uniform3fv(uniforms.offset,offset); gl.uniform3fv(uniforms.scale,scale); gl.uniform3fv(uniforms.color,color);
    gl.drawElements(gl.TRIANGLES,indices.length,gl.UNSIGNED_SHORT,0);
  }
  function draw(t) {
    const jaw = animate ? .35+.3*Math.sin(t/210) : +document.querySelector('#jaw').value;
    const closure = +document.querySelector('#closure').value;
    const opening = jaw * (1-closure);
    const blink = +document.querySelector('#blink').value;
    const yaw = animate ? .09*Math.sin(t/1500) : +document.querySelector('#yaw').value;
    gl.uniform1f(uniforms.yaw,yaw); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
    sphere([0,-1.7,-.2],[1.35,.55,.6],[.17,.29,.36]);
    sphere([0,-1.05,0],[.4,.5,.38],[.68,.45,.32]);
    sphere([0,.1,0],[.88,1.25,.72],[.78,.55,.39]);
    sphere([-.89,.15,0],[.16,.29,.15],[.68,.45,.32]); sphere([.89,.15,0],[.16,.29,.15],[.68,.45,.32]);
    for (const x of [-.31,.31]) {
      sphere([x,.4,.66],[.2,Math.max(.012,.12*(1-blink)),.075],[.94,.94,.87]);
      sphere([x,.4,.735],[.065,Math.max(.008,.072*(1-blink)),.028],[.15,.31,.33]);
      sphere([x,.61,.6],[.22,.034,.05],[.22,.16,.13]);
    }
    sphere([0,.03,.71],[.12,.26,.18],[.75,.51,.35]);
    sphere([0,-.42-opening*.06,.668],[.32,.016+.16*opening,.10],[.15,.055,.04]);
    sphere([0,-.42-opening*.23,.65],[.33,.035,.09],[.54,.29,.22]);
    gl.finish(); // Includes submitted GPU work, rather than only JS command submission.
  }
  canvas.addEventListener('webglcontextlost', event => { event.preventDefault(); contextLost=true; status.textContent='Renderer context lost; reload to retry.'; if(run) run.errors++; });
  document.addEventListener('visibilitychange', () => { if(run && document.hidden) run.hidden++; });
  function percentile(values,p) { const ordered=[...values].sort((a,b)=>a-b); return ordered[Math.max(0,Math.ceil(p*ordered.length)-1)] || 0; }
  async function finishRun(now) {
    const completed=run; run=null;
    const result={schema_version:1,duration_ms:now-completed.start,frames:completed.draws.length,target_fps:30,
      visibility_interruptions:completed.hidden,interval_p50_ms:percentile(completed.intervals,.5),interval_p95_ms:percentile(completed.intervals,.95),
      draw_p95_ms:percentile(completed.draws,.95),estimated_missed_frames:completed.missed,width:1280,height:720,webgl_errors:completed.errors,
      started_at_unix_ms:performance.timeOrigin+completed.start,finished_at_unix_ms:performance.timeOrigin+now};
    document.querySelector('#renderer-report').textContent=JSON.stringify(result,null,2);
    try {
      const response=await fetch('/renderer-benchmark',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(result)});
      if(!response.ok) throw new Error('Report save failed');
      runStatus.textContent=completed.hidden ? 'Saved. The tab was hidden during this run; repeat visibly for a valid foreground measurement.' : 'Measurement saved locally. Draw time includes GPU completion; frame gaps also include browser scheduling.';
    } catch(error) { runStatus.textContent=error.message; }
    buttons.forEach(b=>b.disabled=false);
  }
  function frame(now) {
    if(!contextLost && now+1>=nextFrame) {
      const start=performance.now(); draw(now); const elapsed=performance.now()-start;
      samples.push(elapsed); if(samples.length>120) samples.shift();
      if(run) {
        run.draws.push(elapsed);
        if(run.last!==null) { const delta=now-run.last; run.intervals.push(delta); run.missed+=Math.max(0,Math.round(delta/(1000/30))-1); }
        run.last=now; if(gl.getError()!==gl.NO_ERROR) run.errors++;
        runStatus.textContent=`Measuring ${Math.min(run.duration/1000,(now-run.start)/1000).toFixed(1)} / ${(run.duration/1000).toFixed(0)} seconds. Keep this tab visible.`;
        if(now-run.start>=run.duration) void finishRun(now);
      }
      nextFrame=now+1000/30;
      status.textContent=`1280 × 720 · target 30 fps · draw p95 ${percentile(samples,.95).toFixed(2)} ms`;
    }
    requestAnimationFrame(frame);
  }
  function startRun(seconds) {
    if(run || contextLost) return;
    run={start:performance.now(),duration:seconds*1000,draws:[],intervals:[],last:null,missed:0,hidden:document.hidden?1:0,errors:0};
    buttons.forEach(b=>b.disabled=true);
  }
  document.querySelector('#animate').onclick=event=>{animate=!animate;event.target.textContent=animate?'Stop preview':'Preview movement';};
  buttons[0].onclick=()=>startRun(30); buttons[1].onclick=()=>startRun(600);
  requestAnimationFrame(frame);
  if(new URLSearchParams(location.search).get('benchmark')==='30') startRun(30);
}
try {
  const response=await fetch('/device-benchmark.json');
  if(response.ok) {
    const report=await response.json();
    document.querySelector('#device-report').textContent=report.results.map(result=>`${result.device.toUpperCase()}: ${result.parameters.toLocaleString()} parameters\nInference p95: ${result.warm_inference.p95_ms.toFixed(2)} ms\nTraining step p95: ${result.training_step.p95_ms.toFixed(2)} ms\nFinite gradients: ${result.finite_gradients}`).join('\n\n');
  }
} catch { document.querySelector('#device-report').textContent='Device report is not available yet.'; }
