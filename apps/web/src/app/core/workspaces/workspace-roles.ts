import { WorkspaceRole } from './workspace.models';

/** Jerarquía de roles (ADR-0001): VIEWER < MEMBER < EDITOR < ADMIN < OWNER. */
export const ROLE_ORDER: readonly WorkspaceRole[] = ['VIEWER', 'MEMBER', 'EDITOR', 'ADMIN', 'OWNER'];

/** Nivel 1–5 del rol en la jerarquía. Solo para presentación: la autorización la decide el backend. */
export function roleLevel(role: WorkspaceRole): number {
  return ROLE_ORDER.indexOf(role) + 1;
}

/** ¿El rol alcanza el mínimo? Solo decide qué ofrece la UI; el backend vuelve a autorizar. */
export function hasRoleAtLeast(role: WorkspaceRole | null | undefined, minimum: WorkspaceRole): boolean {
  return role ? roleLevel(role) >= roleLevel(minimum) : false;
}
