import { Routes } from '@angular/router';

import { authGuard } from './core/auth/auth.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./pages/home/home').then((m) => m.Home),
    title: 'CDM — Cloud Document Manager',
  },
  {
    path: 'home',
    redirectTo: '',
    pathMatch: 'full',
  },
  {
    path: 'auth/login',
    loadComponent: () =>
      import('./pages/auth/login/login').then((m) => m.LoginComponent),
    title: 'Iniciar sesión — CDM',
  },
  {
    path: 'auth/register',
    loadComponent: () =>
      import('./pages/auth/register/register').then((m) => m.RegisterComponent),
    title: 'Crear cuenta — CDM',
  },
  {
    path: 'auth/confirm',
    redirectTo: 'auth/login',
    pathMatch: 'full',
  },
  {
    path: 'workspaces/new',
    loadComponent: () =>
      import('./pages/workspaces/create/create').then(
        (m) => m.WorkspaceCreateComponent
      ),
    canActivate: [authGuard],
    title: 'Crear espacio de trabajo — CDM',
  },
  {
    path: 'workspaces/:id/documents',
    loadComponent: () =>
      import('./pages/documents/catalog/catalog').then(
        (m) => m.DocumentCatalogComponent
      ),
    canActivate: [authGuard],
    title: 'Catálogo de documentos — CDM',
  },
  {
    path: 'workspaces/:id',
    redirectTo: 'workspaces/:id/documents',
    pathMatch: 'full',
  },
  {
    path: 'workspaces/:id/members',
    loadComponent: () =>
      import('./pages/workspaces/members/members').then(
        (m) => m.WorkspaceMembersComponent
      ),
    canActivate: [authGuard],
    title: 'Miembros del espacio — CDM',
  },
  {
    path: 'workspaces/:id/upload',
    loadComponent: () =>
      import('./pages/documents/upload/upload').then(
        (m) => m.DocumentUploadComponent
      ),
    canActivate: [authGuard],
    title: 'Cargar documento — CDM',
  },
  { path: '**', redirectTo: '' },
];
