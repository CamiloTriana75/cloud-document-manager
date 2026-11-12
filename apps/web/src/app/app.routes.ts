import { Routes } from '@angular/router';

import { authGuard } from './core/auth/auth.guard';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./pages/home/home').then((m) => m.Home),
    title: 'CDM — Cloud Document Manager',
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
    loadComponent: () =>
      import('./pages/auth/confirm/confirm').then((m) => m.ConfirmComponent),
    title: 'Confirmar cuenta — CDM',
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
    path: 'workspaces/:id/members',
    loadComponent: () =>
      import('./pages/workspaces/members/members').then(
        (m) => m.WorkspaceMembersComponent
      ),
    canActivate: [authGuard],
    title: 'Miembros del espacio — CDM',
  },
  { path: '**', redirectTo: '' },
];
