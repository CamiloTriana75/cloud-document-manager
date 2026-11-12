import { HttpClient } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { catchError, map, Observable, tap, throwError } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AddMemberPayload,
  ApiDataEnvelope,
  CreateWorkspacePayload,
  Workspace,
  WorkspaceMember,
} from './workspace.models';

const ACTIVE_WORKSPACE_STORAGE_KEY = 'cdm_active_workspace_id';

@Injectable({
  providedIn: 'root',
})
export class WorkspaceService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl
    ? `${environment.apiBaseUrl}/api/v1/workspaces`
    : '/api/v1/workspaces';

  readonly workspaces = signal<Workspace[]>([]);
  readonly activeWorkspace = signal<Workspace | null>(null);
  readonly members = signal<WorkspaceMember[]>([]);
  readonly isLoading = signal<boolean>(false);
  readonly error = signal<string | null>(null);

  readonly hasWorkspaces = computed(() => this.workspaces().length > 0);

  readonly canManageMembers = computed(() => {
    const role = this.activeWorkspace()?.role;
    return role === 'OWNER' || role === 'ADMIN';
  });

  constructor() {
    this.restoreActiveWorkspaceFromStorage();
  }

  /**
   * Carga la lista de workspaces accesibles para el usuario autenticado.
   */
  loadWorkspaces(): Observable<Workspace[]> {
    this.isLoading.set(true);
    this.error.set(null);

    return this.http.get<ApiDataEnvelope<Workspace[]>>(this.baseUrl).pipe(
      map((res) => res.data),
      tap((workspaces) => {
        this.workspaces.set(workspaces);
        this.isLoading.set(false);

        // Resolver workspace activo si aún no está fijado
        const currentActive = this.activeWorkspace();
        if (currentActive) {
          const updated = workspaces.find((w) => w.id === currentActive.id);
          if (updated) {
            this.activeWorkspace.set(updated);
            return;
          }
        }

        const storedId = this.getStoredWorkspaceId();
        if (storedId) {
          const match = workspaces.find((w) => w.id === storedId);
          if (match) {
            this.setActiveWorkspace(match);
            return;
          }
        }

        if (workspaces.length > 0) {
          this.setActiveWorkspace(workspaces[0]);
        } else {
          this.setActiveWorkspace(null);
        }
      }),
      catchError((err) => {
        this.isLoading.set(false);
        const msg =
          err?.error?.error?.message || 'Error al cargar los espacios de trabajo.';
        this.error.set(msg);
        return throwError(() => err);
      })
    );
  }

  /**
   * Selecciona el workspace activo y persiste la preferencia.
   */
  setActiveWorkspace(workspace: Workspace | null): void {
    this.activeWorkspace.set(workspace);
    try {
      if (workspace) {
        sessionStorage.setItem(ACTIVE_WORKSPACE_STORAGE_KEY, workspace.id);
      } else {
        sessionStorage.removeItem(ACTIVE_WORKSPACE_STORAGE_KEY);
      }
    } catch {
      // Entornos sin sessionStorage
    }
  }

  /**
   * Crea un nuevo workspace y lo establece como activo.
   */
  createWorkspace(payload: CreateWorkspacePayload): Observable<Workspace> {
    this.isLoading.set(true);
    this.error.set(null);

    return this.http.post<ApiDataEnvelope<Workspace>>(this.baseUrl, payload).pipe(
      map((res) => res.data),
      tap((newWorkspace) => {
        this.workspaces.update((list) => [...list, newWorkspace]);
        this.setActiveWorkspace(newWorkspace);
        this.isLoading.set(false);
      }),
      catchError((err) => {
        this.isLoading.set(false);
        const msg =
          err?.error?.error?.message || 'Error al crear el espacio de trabajo.';
        this.error.set(msg);
        return throwError(() => err);
      })
    );
  }

  /**
   * Obtiene la lista de miembros de un workspace asegurando aislamiento multi-tenant.
   */
  loadMembers(workspaceId: string): Observable<WorkspaceMember[]> {
    this.isLoading.set(true);
    this.error.set(null);

    return this.http
      .get<ApiDataEnvelope<WorkspaceMember[]>>(`${this.baseUrl}/${workspaceId}/members`)
      .pipe(
        map((res) => res.data),
        tap((members) => {
          this.members.set(members);
          this.isLoading.set(false);
        }),
        catchError((err) => {
          this.isLoading.set(false);
          const msg =
            err?.error?.error?.message || 'Error al cargar los miembros del workspace.';
          this.error.set(msg);
          return throwError(() => err);
        })
      );
  }

  /**
   * Agrega o invita un nuevo miembro al workspace (restringido a OWNER / ADMIN).
   */
  addMember(workspaceId: string, payload: AddMemberPayload): Observable<WorkspaceMember> {
    this.isLoading.set(true);
    this.error.set(null);

    return this.http
      .post<ApiDataEnvelope<WorkspaceMember>>(
        `${this.baseUrl}/${workspaceId}/members`,
        payload
      )
      .pipe(
        map((res) => res.data),
        tap((newMember) => {
          this.members.update((list) => [newMember, ...list]);
          this.isLoading.set(false);
        }),
        catchError((err) => {
          this.isLoading.set(false);
          const msg =
            err?.error?.error?.message || 'Error al invitar al miembro al workspace.';
          this.error.set(msg);
          return throwError(() => err);
        })
      );
  }

  private getStoredWorkspaceId(): string | null {
    try {
      return sessionStorage.getItem(ACTIVE_WORKSPACE_STORAGE_KEY);
    } catch {
      return null;
    }
  }

  private restoreActiveWorkspaceFromStorage(): void {
    const storedId = this.getStoredWorkspaceId();
    if (storedId) {
      // Será validado cuando se carguen los workspaces
    }
  }
}
