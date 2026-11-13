import { describe, expect, it } from 'vitest';

import { ringPlacements, washerProfile } from './coil-geometry';

describe('ringPlacements', () => {
  it('reparte los anillos equiespaciados sobre la circunferencia', () => {
    const rings = ringPlacements(4, 2);

    expect(rings.map((r) => r.angle)).toEqual([0, Math.PI / 2, Math.PI, (3 * Math.PI) / 2]);
    const expected = [
      [2, 0],
      [0, 2],
      [-2, 0],
      [0, -2],
    ];
    rings.forEach((ring, index) => {
      expect(ring.position[0]).toBeCloseTo(expected[index][0]);
      expect(ring.position[1]).toBeCloseTo(expected[index][1]);
      expect(ring.position[2]).toBe(0);
    });
  });

  it('orienta cada anillo tangente a la circunferencia', () => {
    const [first, second] = ringPlacements(4, 2);

    expect(first.tangent[0]).toBeCloseTo(0);
    expect(first.tangent[1]).toBeCloseTo(1);
    expect(second.tangent[0]).toBeCloseTo(-1);
    expect(second.tangent[1]).toBeCloseTo(0);
  });
});

describe('washerProfile', () => {
  it('genera un contorno cerrado entre el radio interior y el exterior', () => {
    const points = washerProfile({ innerRadius: 0.4, outerRadius: 0.6, thickness: 0.16, bevel: 0.04 });
    const xs = points.map(([x]) => x);
    const ys = points.map(([, y]) => y);

    expect(Math.min(...xs)).toBeCloseTo(0.4);
    expect(Math.max(...xs)).toBeCloseTo(0.6);
    expect(Math.max(...ys) - Math.min(...ys)).toBeCloseTo(0.16);
    expect(points[0][0]).toBeCloseTo(points[points.length - 1][0]);
    expect(points[0][1]).toBeCloseTo(points[points.length - 1][1]);
  });
});
