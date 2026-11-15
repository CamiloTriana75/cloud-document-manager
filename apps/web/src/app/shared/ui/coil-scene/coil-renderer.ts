/**
 * Renderer de la bobina con three.js. Este módulo solo se carga con `import()` desde
 * CoilSceneComponent: three.js queda en un chunk diferido, fuera del bundle inicial (ADR-0009).
 */
import {
  ACESFilmicToneMapping,
  Color,
  DirectionalLight,
  DoubleSide,
  Fog,
  Group,
  HemisphereLight,
  InstancedMesh,
  LatheGeometry,
  MeshPhysicalMaterial,
  Object3D,
  PerspectiveCamera,
  PMREMGenerator,
  Quaternion,
  Scene,
  SRGBColorSpace,
  Vector2,
  Vector3,
  WebGLRenderer,
} from 'three';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

import { ringPlacements, washerProfile } from './coil-geometry';

export interface CoilRendererOptions {
  readonly ringCount: number;
  readonly maxPixelRatio: number;
  /** false con prefers-reduced-motion: se dibuja un solo fotograma. */
  readonly animate: boolean;
}

export interface CoilRenderer {
  start(): void;
  stop(): void;
  renderOnce(): void;
  resize(width: number, height: number): void;
  dispose(): void;
}

const MAJOR_RADIUS = 2.15;
/** Inclinación de cada anillo sobre su eje radial: da el aspecto de resorte enrollado. */
const RING_TILT = 0.46;
/** Velocidad de avance de los anillos sobre la trayectoria (rad/s). */
const FLOW_SPEED = 0.05;
const CANVAS_COLOR = 0x0d1e20;

export function createCoilRenderer(
  canvas: HTMLCanvasElement,
  options: CoilRendererOptions,
): CoilRenderer {
  const renderer = new WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    powerPreference: 'low-power',
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, options.maxPixelRatio));
  renderer.outputColorSpace = SRGBColorSpace;
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.setClearColor(0x000000, 0);

  const scene = new Scene();
  scene.fog = new Fog(CANVAS_COLOR, 6.4, 11);

  const pmrem = new PMREMGenerator(renderer);
  const environment = pmrem.fromScene(new RoomEnvironment(), 0.04);
  scene.environment = environment.texture;
  pmrem.dispose();

  const camera = new PerspectiveCamera(30, 1, 0.1, 40);
  camera.position.set(0, -1.1, 8.4);
  camera.lookAt(0, 0.4, 0);

  scene.add(new HemisphereLight(0xcff7ee, 0x061716, 0.6));
  const key = new DirectionalLight(0xffffff, 2.1);
  key.position.set(-3, 4.5, 5);
  scene.add(key);
  const rim = new DirectionalLight(0x8fe9d6, 1.3);
  rim.position.set(3.5, -2, -4);
  scene.add(rim);

  const profile = washerProfile({
    innerRadius: 0.4,
    outerRadius: 0.68,
    thickness: 0.2,
    bevel: 0.08,
  }).map(([x, y]) => new Vector2(x, y));
  const geometry = new LatheGeometry(profile, 56);
  const material = new MeshPhysicalMaterial({
    color: new Color('#1f7465'),
    metalness: 0.72,
    roughness: 0.24,
    clearcoat: 1,
    clearcoatRoughness: 0.16,
    envMapIntensity: 1.25,
    side: DoubleSide,
  });

  const rings = new InstancedMesh(geometry, material, options.ringCount);
  const placement = new Object3D();
  const axis = new Vector3(0, 1, 0);
  const tilt = new Quaternion();
  ringPlacements(options.ringCount, MAJOR_RADIUS).forEach((ring, index) => {
    placement.position.set(...ring.position);
    placement.quaternion.setFromUnitVectors(axis, new Vector3(...ring.tangent));
    const radial = new Vector3(ring.position[0], ring.position[1], 0).normalize();
    placement.quaternion.premultiply(tilt.setFromAxisAngle(radial, RING_TILT));
    placement.updateMatrix();
    rings.setMatrixAt(index, placement.matrix);
  });

  const coil = new Group();
  coil.rotation.x = -0.3;
  coil.rotation.y = 0.32;
  coil.add(rings);
  scene.add(coil);

  let running = false;
  let frame = 0;
  let last = 0;

  const draw = () => renderer.render(scene, camera);
  const tick = (now: number) => {
    if (!running) {
      return;
    }
    const delta = last === 0 ? 0 : Math.min((now - last) / 1000, 0.1);
    last = now;
    rings.rotation.z += FLOW_SPEED * delta;
    draw();
    frame = requestAnimationFrame(tick);
  };

  return {
    start() {
      if (running || !options.animate) {
        return;
      }
      running = true;
      last = 0;
      frame = requestAnimationFrame(tick);
    },
    stop() {
      running = false;
      cancelAnimationFrame(frame);
    },
    renderOnce: draw,
    resize(width: number, height: number) {
      if (width <= 0 || height <= 0) {
        return;
      }
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      draw();
    },
    dispose() {
      running = false;
      cancelAnimationFrame(frame);
      geometry.dispose();
      material.dispose();
      environment.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
    },
  };
}
