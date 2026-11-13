/**
 * Geometría pura de la bobina (sin three.js): se prueba en jsdom y la consume el renderer.
 */

export type Vec3 = readonly [number, number, number];

export interface RingPlacement {
  /** Ángulo sobre la circunferencia mayor, en radianes. */
  readonly angle: number;
  /** Centro del anillo sobre la circunferencia (plano XY). */
  readonly position: Vec3;
  /** Dirección tangente: el eje del anillo se alinea con ella para "enhebrar" la trayectoria. */
  readonly tangent: Vec3;
}

/** `count` anillos equiespaciados sobre una circunferencia de radio `majorRadius`. */
export function ringPlacements(count: number, majorRadius: number): RingPlacement[] {
  return Array.from({ length: count }, (_, index) => {
    const angle = (index / count) * Math.PI * 2;
    const cos = Math.cos(angle);
    const sin = Math.sin(angle);
    return {
      angle,
      position: [majorRadius * cos, majorRadius * sin, 0],
      tangent: [-sin, cos, 0],
    };
  });
}

export interface WasherSpec {
  readonly innerRadius: number;
  readonly outerRadius: number;
  readonly thickness: number;
  /** Radio del redondeo de las aristas. */
  readonly bevel: number;
  /** Segmentos por arista redondeada. */
  readonly segments?: number;
}

/**
 * Contorno cerrado (x = radio, y = altura) de una arandela con aristas redondeadas,
 * listo para revolverse con LatheGeometry alrededor del eje Y.
 */
export function washerProfile(spec: WasherSpec): [number, number][] {
  const { innerRadius, outerRadius, thickness, bevel } = spec;
  const segments = spec.segments ?? 5;
  const half = thickness / 2;
  const corners: [cx: number, cy: number, from: number][] = [
    [innerRadius + bevel, -half + bevel, Math.PI],
    [outerRadius - bevel, -half + bevel, Math.PI * 1.5],
    [outerRadius - bevel, half - bevel, 0],
    [innerRadius + bevel, half - bevel, Math.PI * 0.5],
  ];
  const points: [number, number][] = [];
  for (const [cx, cy, from] of corners) {
    for (let step = 0; step <= segments; step++) {
      const angle = from + (step / segments) * (Math.PI / 2);
      points.push([cx + bevel * Math.cos(angle), cy + bevel * Math.sin(angle)]);
    }
  }
  points.push([...points[0]]);
  return points;
}
