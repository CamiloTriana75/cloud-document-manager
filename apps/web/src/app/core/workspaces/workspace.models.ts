/**
 * Modelos y contratos de Workspaces y Membresías en el Frontend (CDM-26 / ADR-0001).
 */

export type WorkspaceRole = 'OWNER' | 'ADMIN' | 'EDITOR' | 'MEMBER' | 'VIEWER';

export type MembershipStatus = 'ACTIVE' | 'INVITED' | 'SUSPENDED';

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  role: WorkspaceRole;
  created_at: string;
  updated_at: string;
}

export interface WorkspaceMember {
  membership_id: string;
  user_id: string;
  email: string;
  display_name: string | null;
  role: WorkspaceRole;
  status: MembershipStatus;
  created_at: string;
}

export interface CreateWorkspacePayload {
  name: string;
  slug?: string;
}

export interface AddMemberPayload {
  email: string;
  role: WorkspaceRole;
}

export interface ApiDataEnvelope<T> {
  data: T;
}
