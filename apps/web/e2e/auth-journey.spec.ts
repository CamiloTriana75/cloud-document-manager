import { expect, test } from '@playwright/test';
import { setupMockApiRoutes } from './fixtures/mock-api';

test.describe('Journey E2E: Autenticación y Sesión de Usuario (CDM-50)', () => {
  test.beforeEach(async ({ page }) => {
    await setupMockApiRoutes(page);
  });

  test('debe mostrar la pantalla de inicio de sesión con controles y títulos accesibles', async ({
    page,
  }) => {
    await page.goto('/auth/login');

    await expect(page.getByRole('heading', { name: 'Iniciar sesión' })).toBeVisible();
    await expect(page.getByLabel('Correo electrónico')).toBeVisible();
    await expect(page.getByLabel('Contraseña')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Entrar a CDM' })).toBeVisible();
  });

  test('debe validar errores de formulario cuando los campos son inválidos', async ({ page }) => {
    await page.goto('/auth/login');

    // Intentar enviar con campos vacíos
    await page.getByRole('button', { name: 'Entrar a CDM' }).click();

    await expect(page.getByText('Ingresa un correo electrónico válido.')).toBeVisible();
    await expect(page.getByText('La contraseña es obligatoria.')).toBeVisible();
  });

  test('debe iniciar sesión exitosamente con credenciales válidas y permitir cerrar sesión', async ({
    page,
  }) => {
    await page.goto('/auth/login');

    await page.getByLabel('Correo electrónico').fill('demo.user@example.com');
    await page.getByLabel('Contraseña').fill('Password123!');
    await page.getByRole('button', { name: 'Entrar a CDM' }).click();

    // Redirige al inicio autenticado
    await expect(page).toHaveURL('/');
    await expect(page.getByRole('banner')).toBeVisible();
    await expect(page.getByText('demo.user', { exact: true })).toBeVisible();

    // Cerrar sesión
    await page.getByRole('button', { name: 'Cerrar sesión' }).click();

    // Redirige de vuelta a login
    await expect(page).toHaveURL(/\/auth\/login/);
  });
});
