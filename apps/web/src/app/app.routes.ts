import { Routes } from '@angular/router';

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
  { path: '**', redirectTo: '' },
];
