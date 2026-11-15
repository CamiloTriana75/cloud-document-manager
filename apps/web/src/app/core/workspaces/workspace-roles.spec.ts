import { describe, expect, it } from 'vitest';

import { hasRoleAtLeast, roleLevel } from './workspace-roles';

describe('jerarquía de roles (ADR-0001)', () => {
  it('ordena VIEWER < MEMBER < EDITOR < ADMIN < OWNER', () => {
    expect(roleLevel('VIEWER')).toBe(1);
    expect(roleLevel('OWNER')).toBe(5);
  });

  it('compara contra un rol mínimo y trata la ausencia de rol como sin permiso', () => {
    expect(hasRoleAtLeast('EDITOR', 'MEMBER')).toBe(true);
    expect(hasRoleAtLeast('EDITOR', 'EDITOR')).toBe(true);
    expect(hasRoleAtLeast('MEMBER', 'EDITOR')).toBe(false);
    expect(hasRoleAtLeast(null, 'VIEWER')).toBe(false);
  });
});
