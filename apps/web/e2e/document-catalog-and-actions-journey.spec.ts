import { expect, test } from '@playwright/test';
import {
  MOCK_DOCUMENTS,
  MOCK_WORKSPACE,
  MOCK_WORKSPACE_VIEWER,
  setupAuthenticatedSession,
  setupMockApiRoutes,
} from './fixtures/mock-api';

test.describe('Journey E2E: Catálogo de Documentos y Acciones de Ciclo de Vida (CDM-50)', () => {
  test('debe listar el catálogo de documentos con metadatos y badges de estado', async ({
    page,
  }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE);
    await setupMockApiRoutes(page, MOCK_WORKSPACE);

    await page.goto(`/workspaces/${MOCK_WORKSPACE.id}/documents`);

    await expect(page.getByRole('heading', { name: 'Catálogo de Documentos' })).toBeVisible();
    await expect(page.getByRole('table', { name: 'Lista de documentos del espacio' })).toBeVisible();

    // Verificación de documentos presentes en la tabla
    await expect(page.getByText('reporte_anual_2026.pdf')).toBeVisible();
    await expect(page.getByText('logo_corporativo.png')).toBeVisible();
    await expect(page.getByText('archivo_corrupto.docx')).toBeVisible();

    // Verificación de badges de estado en el catálogo
    await expect(page.locator('.doc-status-ready').first()).toBeVisible();
    await expect(page.locator('.doc-status-processing').first()).toBeVisible();
    await expect(page.locator('.doc-status-failed').first()).toBeVisible();
  });

  test('debe filtrar documentos mediante búsqueda de texto interactiva', async ({ page }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE);
    await setupMockApiRoutes(page, MOCK_WORKSPACE);

    await page.goto(`/workspaces/${MOCK_WORKSPACE.id}/documents`);

    const searchInput = page.getByPlaceholder('Buscar documento por nombre...');
    await expect(searchInput).toBeVisible();

    // Filtrar por 'reporte'
    await searchInput.fill('reporte');

    // Debe permanecer el documento coincidente
    await expect(page.getByText('reporte_anual_2026.pdf')).toBeVisible();

    // Limpiar búsqueda
    const clearButton = page.getByRole('button', { name: 'Limpiar búsqueda' });
    if (await clearButton.isVisible()) {
      await clearButton.click();
    } else {
      await searchInput.fill('');
    }

    await expect(page.getByText('logo_corporativo.png')).toBeVisible();
  });

  test('debe filtrar documentos mediante las píldoras de estado', async ({ page }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE);
    await setupMockApiRoutes(page, MOCK_WORKSPACE);

    await page.goto(`/workspaces/${MOCK_WORKSPACE.id}/documents`);

    // Clic en la píldora "Listos"
    const readyFilter = page.getByRole('button', { name: /Listos/i });
    await readyFilter.click();
    await expect(readyFilter).toHaveAttribute('aria-pressed', 'true');

    // Clic en "Todos" para restablecer
    const allFilter = page.getByRole('button', { name: /Todos/i });
    await allFilter.click();
    await expect(allFilter).toHaveAttribute('aria-pressed', 'true');
  });

  test('debe abrir y cerrar el modal de detalle técnico accesible', async ({ page }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE);
    await setupMockApiRoutes(page, MOCK_WORKSPACE);

    await page.goto(`/workspaces/${MOCK_WORKSPACE.id}/documents`);

    // Clic en el botón Detalle de la fila de 'reporte_anual_2026.pdf'
    const reportRow = page.getByRole('row', { name: /reporte_anual_2026\.pdf/i });
    await reportRow.getByRole('button', { name: 'Ver detalle técnico del documento' }).click();

    // El diálogo modal debe estar visible
    const modal = page.getByRole('dialog');
    await expect(modal).toBeVisible();
    await expect(page.getByRole('heading', { name: 'reporte_anual_2026.pdf' })).toBeVisible();
    await expect(page.getByText('Metadatos Técnicos (JSONB)')).toBeVisible();
    await expect(page.getByText('Dirección General')).toBeVisible();

    // Cerrar modal con botón accesible
    const closeBtn = page.getByRole('button', { name: 'Cerrar detalle', exact: true });
    await closeBtn.click();
    await expect(modal).not.toBeVisible();
  });

  test('debe permitir solicitar URL prefirmada de descarga para un documento READY', async ({
    page,
  }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE);
    await setupMockApiRoutes(page, MOCK_WORKSPACE);

    await page.goto(`/workspaces/${MOCK_WORKSPACE.id}/documents`);

    // Esperar a que la tabla cargue
    await expect(page.getByRole('table', { name: 'Lista de documentos del espacio' })).toBeVisible();

    // Ubicar botón de descarga del documento listo
    const reportRow = page.getByRole('row', { name: /reporte_anual_2026\.pdf/i });
    const downloadBtn = reportRow.getByRole('button', { name: 'Descargar archivo' });
    await expect(downloadBtn).toBeVisible();
    await downloadBtn.click();

    // No debe saltar error en UI
    await expect(page.locator('.alert-danger')).not.toBeVisible();
  });

  test('debe mostrar confirmación destructiva y ejecutar eliminación lógica', async ({ page }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE);
    await setupMockApiRoutes(page, MOCK_WORKSPACE);

    await page.goto(`/workspaces/${MOCK_WORKSPACE.id}/documents`);

    // Botón eliminar del primer documento
    const deleteButtons = page.getByRole('button', { name: 'Eliminar documento' });
    await deleteButtons.first().click();

    // Modal de confirmación
    const confirmDialog = page.getByRole('dialog');
    await expect(confirmDialog).toBeVisible();
    await expect(page.getByRole('heading', { name: '¿Eliminar documento?' })).toBeVisible();

    // Confirmar eliminación
    const confirmBtn = page.getByRole('button', { name: 'Sí, eliminar' });
    await confirmBtn.click();

    // El modal de confirmación debe cerrarse
    await expect(confirmDialog).not.toBeVisible();
  });

  test('debe respetar permisos de VIEWER ocultando o deshabilitando acciones destructivas', async ({
    page,
  }) => {
    await setupAuthenticatedSession(page, MOCK_WORKSPACE_VIEWER);
    await setupMockApiRoutes(page, MOCK_WORKSPACE_VIEWER);

    await page.goto(`/workspaces/${MOCK_WORKSPACE_VIEWER.id}/documents`);

    // Banner de advertencia para VIEWER
    await expect(page.getByText(/Navegando con rol VIEWER/i)).toBeVisible();

    // El botón de subir documento NO debe estar visible
    await expect(page.getByRole('link', { name: 'Subir documento' })).not.toBeVisible();

    // Los botones de eliminar NO deben estar presentes
    await expect(page.getByRole('button', { name: 'Eliminar documento' })).not.toBeVisible();
  });
});
