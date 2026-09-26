// Tibi's stage animation (OBS S13): smoke-like particles that follow Tibi's voice and the speaker's.
//
// The particle motion is adapted from "The Spirit" by Edan Kwan (https://github.com/edankwan/The-Spirit),
// MIT licence, Copyright (c) 2015 Edan Kwan: positions live in a float texture and each frame a shader pulls every
// particle towards a moving point and pushes it along curl noise, respawning it when its life runs out. The simplex
// noise with derivatives is Ashima Arts / Stefan Gustavson's (webgl-noise, MIT). The owner's Board Game Assistant
// drove it from the assistant's voice; here the same idea follows Tibi's voice as it plays, and the microphone
// while the person speaks. It is drawn as soft glowing points (no shadows, blur or bloom passes) and kept to 16k
// particles, because Tibi's own voice model shares the GPU.
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

export type StageState = "idle" | "starting" | "listening" | "thinking" | "speaking" | "paused";

export interface Levels {
  tibi: number;
  mic: number;
  brightness: number;
}

const SIZE = 128; // 128 × 128 = 16,384 particles
const RADIUS = 0.48; // The Spirit's radius for this amount

// Per state: the core colour, the fading colour, how lively the motion is, and how bright.
const LOOK: Record<StageState, { core: string; fade: string; motion: number; glow: number }> = {
  idle: { core: "#8b93ff", fade: "#2a2466", motion: 0.35, glow: 0.55 },
  starting: { core: "#7c83d6", fade: "#1f1b4d", motion: 0.25, glow: 0.4 },
  listening: { core: "#5eead4", fade: "#134e4a", motion: 0.5, glow: 0.65 },
  thinking: { core: "#b794ff", fade: "#3b1f6e", motion: 0.9, glow: 0.75 },
  speaking: { core: "#ff4d9d", fade: "#5a0f35", motion: 0.6, glow: 0.85 },
  paused: { core: "#64748b", fade: "#1e293b", motion: 0.12, glow: 0.3 },
};

const NOISE = /* glsl */ `
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
float mod289(float x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x * 34.0) + 1.0) * x); }
float permute(float x) { return mod289(((x * 34.0) + 1.0) * x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
float taylorInvSqrt(float r) { return 1.79284291400159 - 0.85373472095314 * r; }
vec4 grad4(float j, vec4 ip) {
  const vec4 ones = vec4(1.0, 1.0, 1.0, -1.0);
  vec4 p, s;
  p.xyz = floor(fract(vec3(j) * ip.xyz) * 7.0) * ip.z - 1.0;
  p.w = 1.5 - dot(abs(p.xyz), ones.xyz);
  s = vec4(lessThan(p, vec4(0.0)));
  p.xyz = p.xyz + (s.xyz * 2.0 - 1.0) * s.www;
  return p;
}
#define F4 0.309016994374947451
vec4 simplexNoiseDerivatives(vec4 v) {
  const vec4 C = vec4(0.138196601125011, 0.276393202250021, 0.414589803375032, -0.447213595499958);
  vec4 i = floor(v + dot(v, vec4(F4)));
  vec4 x0 = v - i + dot(i, C.xxxx);
  vec4 i0;
  vec3 isX = step(x0.yzw, x0.xxx);
  vec3 isYZ = step(x0.zww, x0.yyz);
  i0.x = isX.x + isX.y + isX.z;
  i0.yzw = 1.0 - isX;
  i0.y += isYZ.x + isYZ.y;
  i0.zw += 1.0 - isYZ.xy;
  i0.z += isYZ.z;
  i0.w += 1.0 - isYZ.z;
  vec4 i3 = clamp(i0, 0.0, 1.0);
  vec4 i2 = clamp(i0 - 1.0, 0.0, 1.0);
  vec4 i1 = clamp(i0 - 2.0, 0.0, 1.0);
  vec4 x1 = x0 - i1 + C.xxxx;
  vec4 x2 = x0 - i2 + C.yyyy;
  vec4 x3 = x0 - i3 + C.zzzz;
  vec4 x4 = x0 + C.wwww;
  i = mod289(i);
  float j0 = permute(permute(permute(permute(i.w) + i.z) + i.y) + i.x);
  vec4 j1 = permute(permute(permute(permute(
      i.w + vec4(i1.w, i2.w, i3.w, 1.0)) + i.z + vec4(i1.z, i2.z, i3.z, 1.0))
      + i.y + vec4(i1.y, i2.y, i3.y, 1.0)) + i.x + vec4(i1.x, i2.x, i3.x, 1.0));
  vec4 ip = vec4(1.0 / 294.0, 1.0 / 49.0, 1.0 / 7.0, 0.0);
  vec4 p0 = grad4(j0, ip);
  vec4 p1 = grad4(j1.x, ip);
  vec4 p2 = grad4(j1.y, ip);
  vec4 p3 = grad4(j1.z, ip);
  vec4 p4 = grad4(j1.w, ip);
  vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  p4 *= taylorInvSqrt(dot(p4, p4));
  vec3 values0 = vec3(dot(p0, x0), dot(p1, x1), dot(p2, x2));
  vec2 values1 = vec2(dot(p3, x3), dot(p4, x4));
  vec3 m0 = max(0.5 - vec3(dot(x0, x0), dot(x1, x1), dot(x2, x2)), 0.0);
  vec2 m1 = max(0.5 - vec2(dot(x3, x3), dot(x4, x4)), 0.0);
  vec3 temp0 = -6.0 * m0 * m0 * values0;
  vec2 temp1 = -6.0 * m1 * m1 * values1;
  vec3 mmm0 = m0 * m0 * m0;
  vec2 mmm1 = m1 * m1 * m1;
  float dx = temp0[0] * x0.x + temp0[1] * x1.x + temp0[2] * x2.x + temp1[0] * x3.x + temp1[1] * x4.x + mmm0[0] * p0.x + mmm0[1] * p1.x + mmm0[2] * p2.x + mmm1[0] * p3.x + mmm1[1] * p4.x;
  float dy = temp0[0] * x0.y + temp0[1] * x1.y + temp0[2] * x2.y + temp1[0] * x3.y + temp1[1] * x4.y + mmm0[0] * p0.y + mmm0[1] * p1.y + mmm0[2] * p2.y + mmm1[0] * p3.y + mmm1[1] * p4.y;
  float dz = temp0[0] * x0.z + temp0[1] * x1.z + temp0[2] * x2.z + temp1[0] * x3.z + temp1[1] * x4.z + mmm0[0] * p0.z + mmm0[1] * p1.z + mmm0[2] * p2.z + mmm1[0] * p3.z + mmm1[1] * p4.z;
  float dw = temp0[0] * x0.w + temp0[1] * x1.w + temp0[2] * x2.w + temp1[0] * x3.w + temp1[1] * x4.w + mmm0[0] * p0.w + mmm0[1] * p1.w + mmm0[2] * p2.w + mmm1[0] * p3.w + mmm1[1] * p4.w;
  return vec4(dx, dy, dz, dw) * 49.0;
}
vec3 curl(in vec3 p, in float noiseTime, in float persistence) {
  vec4 xN = vec4(0.0), yN = vec4(0.0), zN = vec4(0.0);
  for (int i = 0; i < 3; ++i) {
    float twoPowI = pow(2.0, float(i));
    float scale = 0.5 * twoPowI * pow(persistence, float(i));
    xN += simplexNoiseDerivatives(vec4(p * twoPowI, noiseTime)) * scale;
    yN += simplexNoiseDerivatives(vec4((p + vec3(123.4, 129845.6, -1239.1)) * twoPowI, noiseTime)) * scale;
    zN += simplexNoiseDerivatives(vec4((p + vec3(-9519.0, 9051.0, -123.0)) * twoPowI, noiseTime)) * scale;
  }
  return vec3(zN[1] - yN[2], xN[2] - zN[0], yN[0] - xN[1]);
}
`;

const QUAD_VERT = /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }
`;

const POSITION_FRAG = /* glsl */ `
uniform sampler2D texturePosition;
uniform sampler2D textureDefaultPosition;
uniform float time;
uniform float speed;
uniform float dieSpeed;
uniform float radius;
uniform float curlSize;
uniform float attraction;
uniform vec3 attractor;
varying vec2 vUv;
${NOISE}
void main() {
  vec4 positionInfo = texture2D(texturePosition, vUv);
  vec3 position = positionInfo.xyz;
  float life = positionInfo.a - dieSpeed;
  if (life < 0.0) {
    positionInfo = texture2D(textureDefaultPosition, vUv);
    position = positionInfo.xyz * (1.0 + sin(time * 15.0) * 0.2) * 0.4 * radius + attractor;
    life = 0.5 + fract(positionInfo.w * 21.4131 + time);
  } else {
    vec3 delta = attractor - position;
    position += delta * (0.005 + life * 0.01) * attraction * (1.0 - smoothstep(50.0, 350.0, length(delta))) * speed;
    position += curl(position * curlSize, time, 0.1 + (1.0 - life) * 0.1) * speed;
  }
  gl_FragColor = vec4(position, life);
}
`;

const POINTS_VERT = /* glsl */ `
uniform sampler2D texturePosition;
uniform float sizeScale;
varying float vLife;
void main() {
  vec4 positionInfo = texture2D(texturePosition, position.xy);
  vec4 mvPosition = modelViewMatrix * vec4(positionInfo.xyz, 1.0);
  vLife = positionInfo.w;
  gl_PointSize = sizeScale * 1300.0 / length(mvPosition.xyz) * smoothstep(0.0, 0.2, positionInfo.w);
  gl_Position = projectionMatrix * mvPosition;
}
`;

const POINTS_FRAG = /* glsl */ `
uniform vec3 color1;
uniform vec3 color2;
uniform float opacity;
varying float vLife;
void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = dot(c, c);
  if (d > 0.25) discard;
  float soft = smoothstep(0.25, 0.0, d);
  vec3 colour = mix(color2, color1, smoothstep(0.0, 0.7, vLife));
  gl_FragColor = vec4(colour, soft * opacity * smoothstep(0.0, 0.25, vLife));
}
`;

function supported(): boolean {
  try {
    const canvas = document.createElement("canvas");
    const gl = canvas.getContext("webgl2");
    return Boolean(gl && gl.getExtension("EXT_color_buffer_float"));
  } catch {
    return false;
  }
}

function reducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/** The particle stage. ``levels`` is read every frame, so the page does not re-render to animate it. */
export function Spirit({ state, levels }: { state: StageState; levels: () => Levels }) {
  const host = useRef<HTMLDivElement>(null);
  const stateRef = useRef(state);
  const levelsRef = useRef(levels);
  const [mode] = useState<"particles" | "orb">(() => (supported() && !reducedMotion() ? "particles" : "orb"));
  stateRef.current = state;
  levelsRef.current = levels;

  useEffect(() => {
    const element = host.current;
    if (!element || mode !== "particles") return;
    const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true, powerPreference: "low-power" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.setClearColor(0x000000, 0);
    element.appendChild(renderer.domElement);

    // Simulation: positions in a float texture, updated by a full-screen pass, ping-ponged between two targets.
    const target = () =>
      new THREE.WebGLRenderTarget(SIZE, SIZE, {
        type: THREE.FloatType,
        format: THREE.RGBAFormat,
        minFilter: THREE.NearestFilter,
        magFilter: THREE.NearestFilter,
        depthBuffer: false,
        stencilBuffer: false,
      });
    let read = target();
    let write = target();
    const start = new Float32Array(SIZE * SIZE * 4);
    for (let i = 0; i < SIZE * SIZE; i++) {
      const r = (0.5 + Math.random() * 0.5) * 50;
      const phi = (Math.random() - 0.5) * Math.PI;
      const theta = Math.random() * Math.PI * 2;
      start.set([r * Math.cos(theta) * Math.cos(phi), r * Math.sin(phi), r * Math.sin(theta) * Math.cos(phi), Math.random()], i * 4);
    }
    const defaults = new THREE.DataTexture(start, SIZE, SIZE, THREE.RGBAFormat, THREE.FloatType);
    defaults.minFilter = defaults.magFilter = THREE.NearestFilter;
    defaults.needsUpdate = true;
    const simulation = new THREE.ShaderMaterial({
      uniforms: {
        texturePosition: { value: defaults },
        textureDefaultPosition: { value: defaults },
        time: { value: 0 },
        speed: { value: 1 },
        dieSpeed: { value: 0.015 },
        radius: { value: RADIUS },
        curlSize: { value: 0.02 },
        attraction: { value: 1 },
        attractor: { value: new THREE.Vector3() },
      },
      vertexShader: QUAD_VERT,
      fragmentShader: POSITION_FRAG,
      depthTest: false,
      depthWrite: false,
    });
    const quadScene = new THREE.Scene();
    const quadCamera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
    const quad = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), simulation);
    quadScene.add(quad);

    // Drawing: one point per particle, placed from the position texture.
    const lookup = new Float32Array(SIZE * SIZE * 3);
    for (let i = 0; i < SIZE * SIZE; i++) {
      lookup.set([((i % SIZE) + 0.5) / SIZE, (Math.floor(i / SIZE) + 0.5) / SIZE, 0], i * 3);
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute("position", new THREE.BufferAttribute(lookup, 3));
    const drawing = new THREE.ShaderMaterial({
      uniforms: {
        texturePosition: { value: defaults },
        sizeScale: { value: 1 },
        color1: { value: new THREE.Color(LOOK.idle.core) },
        color2: { value: new THREE.Color(LOOK.idle.fade) },
        opacity: { value: 0.12 },
      },
      vertexShader: POINTS_VERT,
      fragmentShader: POINTS_FRAG,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const points = new THREE.Points(geometry, drawing);
    points.frustumCulled = false;
    const scene = new THREE.Scene();
    scene.add(points);
    const camera = new THREE.PerspectiveCamera(45, 1, 1, 3000);
    camera.position.set(0, 70, 430);
    camera.lookAt(0, 0, 0);

    const resize = () => {
      const width = Math.max(1, element.clientWidth);
      const height = Math.max(1, element.clientHeight);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      drawing.uniforms.sizeScale.value = renderer.getPixelRatio() * Math.min(1.4, Math.max(0.7, height / 420));
    };
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    resize();

    const core = new THREE.Color(LOOK.idle.core);
    const fade = new THREE.Color(LOOK.idle.fade);
    const hot = new THREE.Color("#ffb38a");
    const white = new THREE.Color("#ffffff");
    const aim = new THREE.Color();
    let energy = 0;
    let angle = 0;
    let last = performance.now();
    let frame = 0;
    let first = true;
    const attractor = simulation.uniforms.attractor.value as THREE.Vector3;
    const goal = new THREE.Vector3();

    const tick = (now: number, once = false) => {
      if (!once) {
        frame = requestAnimationFrame(tick);
        if (document.hidden) return;
      }
      const dt = Math.min(50, now - last);
      last = now;
      const ratio = dt / 16.667;
      const look = LOOK[stateRef.current];
      const { tibi, mic, brightness } = levelsRef.current();
      // Tibi's voice drives the speaking look; the microphone drives listening; otherwise a slow breath.
      const speaking = tibi > 0.015 || stateRef.current === "speaking";
      const level = speaking ? tibi : stateRef.current === "listening" ? mic * 1.6 : 0;
      const breath = stateRef.current === "thinking" ? 0.25 + 0.15 * Math.sin(now / 260) : 0.06 + 0.04 * Math.sin(now / 1400);
      const wanted = Math.min(1, Math.max(level * 2.2, breath));
      energy += (wanted - energy) * (wanted > energy ? 0.3 : 0.06) * ratio;

      // The point the smoke follows: The Spirit's own figure (a wide loop that rises and falls), so the particles
      // trail behind it as smoke. It sweeps faster and wider as the voice rises.
      angle += dt * 0.001 * (0.55 + look.motion * 0.5 + energy * 1.2);
      const wide = 150 + energy * 50;
      const tall = 50 + energy * 30;
      goal.set(Math.cos(angle) * wide, Math.cos(angle * 4) * tall, Math.sin(angle * 2) * wide * 0.6);
      attractor.lerp(goal, 0.12 * ratio);

      const s = simulation.uniforms;
      s.time.value += dt * 0.001;
      s.speed.value = (0.45 + look.motion * 0.6 + energy * 1.6) * ratio;
      s.dieSpeed.value = 0.009 * (0.85 + energy * 0.9) * ratio; // longer lives than The Spirit's 0.015: longer trails
      s.curlSize.value = 0.012 + energy * 0.03;
      s.attraction.value = 1 + energy * 4;

      // Colour: the state's own, warming towards peach and then white as Tibi's voice rises and brightens.
      aim.set(speaking ? LOOK.speaking.core : look.core);
      if (speaking) aim.lerp(hot, Math.min(1, energy * 0.9)).lerp(white, Math.max(0, energy - 0.55) * (0.6 + brightness));
      core.lerp(aim, 0.06 * ratio);
      fade.lerp(aim.set(speaking ? LOOK.speaking.fade : look.fade), 0.05 * ratio);
      drawing.uniforms.color1.value.copy(core);
      drawing.uniforms.color2.value.copy(fade);
      drawing.uniforms.opacity.value = look.glow * (0.2 + energy * 0.35);
      points.rotation.y += dt * 0.00008 * (1 + energy * 3);
      points.scale.setScalar(1 + energy * 0.18);

      simulation.uniforms.texturePosition.value = first ? defaults : read.texture;
      first = false;
      renderer.setRenderTarget(write);
      renderer.render(quadScene, quadCamera);
      renderer.setRenderTarget(null);
      [read, write] = [write, read];
      drawing.uniforms.texturePosition.value = read.texture;
      renderer.render(scene, camera);
    };
    tick(performance.now(), true); // the first frame at once: the stage is never blank, and shader errors show early
    frame = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      renderer.dispose();
      read.dispose();
      write.dispose();
      defaults.dispose();
      geometry.dispose();
      drawing.dispose();
      simulation.dispose();
      quad.geometry.dispose();
      renderer.domElement.remove();
    };
  }, [mode]);

  // Without WebGL, or when the system asks for less motion: a soft orb that breathes with the voice.
  const orb = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (mode !== "orb") return;
    let frame = 0;
    let energy = 0;
    const tick = () => {
      frame = requestAnimationFrame(tick);
      const { tibi, mic } = levelsRef.current();
      const wanted = Math.min(1, Math.max(tibi, stateRef.current === "listening" ? mic : 0) * 2);
      energy += (wanted - energy) * 0.15;
      if (orb.current) orb.current.style.transform = `scale(${1 + energy * 0.25})`;
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [mode]);

  return (
    <div ref={host} className={`tibi-spirit tibi-spirit--${state}`} aria-hidden="true">
      {mode === "orb" ? <div ref={orb} className="tibi-orb" /> : null}
    </div>
  );
}

export default Spirit;
