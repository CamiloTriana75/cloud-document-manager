import { expect, test } from '@playwright/test';
import {
  MOCK_WORKSPACE,
  MOCK_WORKSPACE_VIEWER,
  setupAuthenticatedSession,
  setupMockApiRoutes,
} from './fixtures/mock-api';

test.describe('Journey E2E: Carga de Documentos y Progreso a S3 (CDM-50)', () => {
  test('debe mostrar la zona de carga dropzone accesible en workspace activo', async ({ page }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE);
    await setupMockApiRoutes(page, MOCK_WORKSPACE);

    await page.goto(`/workspaces/${MOCK_WORKSPACE.id}/upload`);

    await expect(page.getByRole('heading', { name: 'Carga directa y segura a la nube' })).toBeVisible();
    await expect(page.getByRole('region', { name: /Zona de carga/ })).toBeVisible();
    await expect(page.getByText('Formatos admitidos: PDF, PNG, JPG, TXT, MD, CSV, JSON, DOCX, XLSX')).toBeVisible();
  });

  test('debe completar el flujo de carga a S3 con progreso y confirmación', async ({ page }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE);
    await setupMockApiRoutes(page, MOCK_WORKSPACE);

    await page.goto(`/workspaces/${MOCK_WORKSPACE.id}/upload`);

    // Seleccionar archivo PDF válido mediante el input oculto
    const fileInput = page.locator('#file-upload-input');
    await fileInput.setInputFiles({
      name: 'reporte_ventas_2026.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 test document binary content'),
    });

    // Archivo seleccionado listo para subir
    await expect(page.getByText('reporte_ventas_2026.pdf')).toBeVisible();
    const startButton = page.getByRole('button', { name: 'Iniciar carga segura a S3' });
    await expect(startButton).toBeVisible();
    await startButton.click();

    // Verificación de resultado exitoso
    await expect(page.getByRole('heading', { name: '¡Documento cargado exitosamente!' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Ver en el catálogo' })).toBeVisible();
  });

  test('debe mostrar un mensaje de error accesible cuando el formato no está permitido', async ({ page }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE);
    await setupMockApiRoutes(page, MOCK_WORKSPACE);

    await page.goto(`/workspaces/${MOCK_WORKSPACE.id}/upload`);

    const fileInput = page.locator('#file-upload-input');
    await fileInput.setInputFiles({
      name: 'archivo_peligroso.exe',
      mimeType: 'application/x-msdownload',
      buffer: Buffer.from('fake binary executable'),
    });

    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.getByText(/no está permitido/i)).toBeVisible();
  });

  test('debe deshabilitar la carga y mostrar advertencia para usuarios con rol VIEWER', async ({ page }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE_VIEWER);
    await setupMockApiRoutes(page, MOCK_WORKSPACE_VIEWER);

    await page.goto(`/workspaces/${MOCK_WORKSPACE_VIEWER.id}/upload`);

    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page.getByText('Permiso insuficiente para carga')).toBeVisible();
    await expect(page.locator('#file-upload-input')).toBeDisabled();
  });
});
