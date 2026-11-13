import { expect, test } from '@playwright/test';
import {
  MOCK_USER,
  MOCK_WORKSPACE,
  MOCK_WORKSPACE_VIEWER,
  setupAuthenticatedSession,
  setupMockApiRoutes,
} from './fixtures/mock-api';

test.describe('Journey E2E: Gestión de Workspaces y Miembros (CDM-50)', () => {
  test('debe permitir crear un nuevo workspace y redirigir al catálogo', async ({ page }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE);
    await setupMockApiRoutes(page, MOCK_WORKSPACE);

    await page.goto('/workspaces/new');

    await expect(page.getByRole('heading', { name: 'Crear espacio de trabajo' })).toBeVisible();

    const nameInput = page.locator('#ws-name');
    const slugInput = page.locator('#ws-slug');
    const submitBtn = page.getByRole('button', { name: 'Crear espacio de trabajo' });

    // El botón debe estar deshabilitado inicialmente por validación requerida
    await expect(submitBtn).toBeDisabled();

    // Rellenar formulario con datos válidos
    await nameInput.fill('Innovación Digital');
    await slugInput.fill('innovacion-digital');

    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Redirección a la vista principal tras la creación
    await expect(page).toHaveURL('http://localhost:4200/');
  });

  test('debe validar errores de validación de slug y campos obligatorios', async ({ page }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE);
    await setupMockApiRoutes(page, MOCK_WORKSPACE);

    await page.goto('/workspaces/new');

    const nameInput = page.locator('#ws-name');
    const slugInput = page.locator('#ws-slug');

    // Tocar campo y dejarlo vacío
    await nameInput.focus();
    await slugInput.focus();

    await expect(page.getByText('El nombre del espacio es obligatorio.')).toBeVisible();

    // Slug con caracteres inválidos (mayúsculas o espacios)
    await slugInput.fill('Slug Con Espacios!');
    await nameInput.focus();

    await expect(
      page.getByText('El slug solo puede contener letras minúsculas, números y guiones sencillos.'),
    ).toBeVisible();
  });

  test('debe listar los integrantes del workspace y permitir agregar nuevo miembro', async ({
    page,
  }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE);
    await setupMockApiRoutes(page, MOCK_WORKSPACE);

    await page.goto(`/workspaces/${MOCK_WORKSPACE.id}/members`);

    await expect(page.getByRole('heading', { name: /Miembros de Empresa Demo/i })).toBeVisible();

    // Miembro existente en la tabla
    await expect(page.getByText(MOCK_USER.email)).toBeVisible();

    // Formulario de invitación para OWNER
    await expect(page.getByRole('heading', { name: 'Invitar a un nuevo miembro' })).toBeVisible();

    const emailInput = page.locator('#member-email');
    const roleSelect = page.locator('#member-role');
    const inviteBtn = page.getByRole('button', { name: 'Agregar miembro' });

    await emailInput.fill('nuevo.editor@cdm.example.com');
    await roleSelect.selectOption('EDITOR');

    await inviteBtn.click();

    // Mensaje de éxito
    await expect(page.getByRole('status')).toBeVisible();
  });

  test('debe ocultar el formulario de invitación cuando el usuario tiene rol VIEWER', async ({
    page,
  }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE_VIEWER);
    await setupMockApiRoutes(page, MOCK_WORKSPACE_VIEWER);

    await page.goto(`/workspaces/${MOCK_WORKSPACE_VIEWER.id}/members`);

    // Debe ver el listado
    await expect(page.getByText(MOCK_USER.email)).toBeVisible();

    // NO debe ver el formulario de invitar
    await expect(page.getByRole('heading', { name: 'Invitar a un nuevo miembro' })).not.toBeVisible();
    await expect(page.locator('#member-email')).not.toBeVisible();
  });
});
