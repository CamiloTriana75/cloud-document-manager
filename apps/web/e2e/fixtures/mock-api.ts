import { Page } from '@playwright/test';

export const MOCK_USER = {
  sub: 'sub-test-12345',
  email: 'tester@cdm.example.com',
  name: 'Tester',
  emailVerified: true,
};

export const MOCK_TOKENS = {
  accessToken: 'mock-jwt-access-token',
  idToken: 'mock-jwt-id-token',
  refreshToken: 'mock-jwt-refresh-token',
  expiresAt: Date.now() + 3600 * 1000,
};

export const MOCK_WORKSPACE = {
  id: '00000000-0000-4000-a000-000000000001',
  name: 'Empresa Demo',
  slug: 'empresa-demo',
  role: 'OWNER',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

export const MOCK_WORKSPACE_VIEWER = {
  id: '00000000-0000-4000-a000-000000000002',
  name: 'Espacio Solo Lectura',
  slug: 'solo-lectura',
  role: 'VIEWER',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

export const MOCK_DOCUMENTS = [
  {
    id: '11111111-1111-4000-a000-000000000001',
    workspace_id: MOCK_WORKSPACE.id,
    uploaded_by: MOCK_USER.sub,
    original_filename: 'reporte_anual_2026.pdf',
    storage_key: `tenants/${MOCK_WORKSPACE.id}/documents/11111111-1111-4000-a000-000000000001/reporte_anual_2026.pdf`,
    content_type: 'application/pdf',
    size_bytes: 1048576,
    checksum_sha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    status: 'READY',
    technical_metadata: { page_count: 24, author: 'Dirección General' },
    created_at: '2026-11-10T10:00:00Z',
    updated_at: '2026-11-10T10:05:00Z',
  },
  {
    id: '11111111-1111-4000-a000-000000000002',
    workspace_id: MOCK_WORKSPACE.id,
    uploaded_by: MOCK_USER.sub,
    original_filename: 'logo_corporativo.png',
    storage_key: `tenants/${MOCK_WORKSPACE.id}/documents/11111111-1111-4000-a000-000000000002/logo_corporativo.png`,
    content_type: 'image/png',
    size_bytes: 204800,
    checksum_sha256: null,
    status: 'PROCESSING',
    technical_metadata: { width: 800, height: 600 },
    created_at: '2026-11-11T14:30:00Z',
    updated_at: '2026-11-11T14:30:00Z',
  },
  {
    id: '11111111-1111-4000-a000-000000000003',
    workspace_id: MOCK_WORKSPACE.id,
    uploaded_by: MOCK_USER.sub,
    original_filename: 'archivo_corrupto.docx',
    storage_key: `tenants/${MOCK_WORKSPACE.id}/documents/11111111-1111-4000-a000-000000000003/archivo_corrupto.docx`,
    content_type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    size_bytes: 51200,
    checksum_sha256: null,
    status: 'FAILED',
    technical_metadata: { error: 'Estructura ZIP corrupta' },
    created_at: '2026-11-12T09:15:00Z',
    updated_at: '2026-11-12T09:16:00Z',
  },
];

/**
 * Prepara la sesión autenticada en storage antes de navegar.
 */
export async function setupAuthenticatedSession(
  page: Page,
  workspace = MOCK_WORKSPACE,
): Promise<void> {
  await page.addInitScript(
    ({ tokens, workspaceId }) => {
      window.sessionStorage.setItem('cdm_auth_tokens', JSON.stringify(tokens));
      window.sessionStorage.setItem('cdm_active_workspace_id', workspaceId);
      window.localStorage.setItem('cdm_auth_tokens', JSON.stringify(tokens));
      window.localStorage.setItem('cdm_active_workspace_id', workspaceId);
    },
    { tokens: MOCK_TOKENS, workspaceId: workspace.id },
  );
}

/**
 * Intercepta todas las llamadas de la API REST de CDM para pruebas reproducibles.
 */
export async function setupMockApiRoutes(page: Page, workspace = MOCK_WORKSPACE): Promise<void> {
  // 1. Workspaces
  await page.route(/\/api\/v1\/workspaces$/, async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: [workspace] }),
      });
    } else if (route.request().method() === 'POST') {
      const payload = route.request().postDataJSON() || {};
      const newWs = {
        id: '00000000-0000-4000-a000-000000000099',
        name: payload.name || 'Nuevo Workspace',
        slug: payload.slug || 'nuevo-workspace',
        role: 'OWNER',
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ data: newWs }),
      });
    } else {
      await route.continue();
    }
  });

  // 2. Miembros del workspace
  await page.route(new RegExp(`/api/v1/workspaces/${workspace.id}/members`), async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [
            {
              id: '22222222-2222-4000-a000-000000000001',
              workspace_id: workspace.id,
              user_id: MOCK_USER.sub,
              email: MOCK_USER.email,
              display_name: MOCK_USER.name,
              role: workspace.role,
              status: 'ACTIVE',
              created_at: '2026-11-01T00:00:00Z',
              updated_at: '2026-11-01T00:00:00Z',
            },
          ],
        }),
      });
    } else if (route.request().method() === 'POST') {
      const payload = route.request().postDataJSON() || {};
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            id: '22222222-2222-4000-a000-000000000002',
            workspace_id: workspace.id,
            user_id: 'sub-new-member',
            email: payload.email || 'new@cdm.example.com',
            display_name: (payload.email || 'new').split('@')[0],
            role: payload.role || 'MEMBER',
            status: 'ACTIVE',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        }),
      });
    } else {
      await route.continue();
    }
  });

  // 3. Sesión de carga prefirmada (upload-sessions)
  await page.route(
    new RegExp(`/api/v1/workspaces/${workspace.id}/upload-sessions`),
    async (route) => {
      let payload: Record<string, any> = {};
      try {
        payload = route.request().postDataJSON() || {};
      } catch {
        payload = {};
      }

      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            upload_session_id: '33333333-3333-4000-a000-000000000001',
            document_id: '44444444-4444-4000-a000-000000000001',
            upload_url: 'https://test-cdm-documents.s3.us-east-1.amazonaws.com/mock-upload-url',
            storage_key: `tenants/${workspace.id}/documents/44444444-4444-4000-a000-000000000001/${payload['original_filename'] || 'reporte_ventas_2026.pdf'}`,
            content_type: payload['content_type'] || 'application/pdf',
            size_bytes: payload['size_bytes'] || 1024,
            expires_at: new Date(Date.now() + 900 * 1000).toISOString(),
            expires_in_seconds: 900,
            required_headers: { 'Content-Type': payload['content_type'] || 'application/pdf' },
          },
        }),
      });
    },
  );

  // 4. Subida directa binaria a S3 (PUT y preflight CORS)
  await page.route(/https:\/\/test-cdm-documents\.s3/, async (route) => {
    await route.fulfill({
      status: 200,
      headers: {
        'access-control-allow-origin': '*',
        'access-control-allow-methods': 'PUT, GET, OPTIONS',
        'access-control-allow-headers': '*',
        ETag: '"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"',
      },
    });
  });

  // 5. Endpoints de Documentos (catálogo, detalle, complete, download-url, delete)
  await page.route(new RegExp(`/api/v1/workspaces/${workspace.id}/documents`), async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();

    // 5.1 Confirmación de subida (/complete)
    if (url.pathname.endsWith('/complete') && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            id: '44444444-4444-4000-a000-000000000001',
            workspace_id: workspace.id,
            uploaded_by: MOCK_USER.sub,
            original_filename: 'reporte_ventas_2026.pdf',
            content_type: 'application/pdf',
            size_bytes: 1024,
            status: 'READY',
            technical_metadata: { page_count: 5 },
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        }),
      });
      return;
    }

    // 5.2 Emisión de URL de descarga (/download-url)
    if (url.pathname.endsWith('/download-url') && method === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            document_id: '11111111-1111-4000-a000-000000000001',
            original_filename: 'reporte_anual_2026.pdf',
            download_url: 'https://test-cdm-documents.s3.us-east-1.amazonaws.com/mock-download-url',
            expires_in_seconds: 900,
          },
        }),
      });
      return;
    }

    // 5.3 Eliminación lógica
    if (method === 'DELETE') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: { message: 'Documento eliminado lógicamente.' } }),
      });
      return;
    }

    // 5.4 Consultas GET (detalle por ID o listado con filtros)
    if (method === 'GET') {
      const segments = url.pathname.split('/');
      const lastSegment = segments[segments.length - 1];

      // Consulta de un documento individual
      if (lastSegment && lastSegment !== 'documents' && !lastSegment.includes('?')) {
        const doc = MOCK_DOCUMENTS.find((d) => d.id === lastSegment) || {
          id: lastSegment,
          workspace_id: workspace.id,
          uploaded_by: MOCK_USER.sub,
          original_filename: 'reporte_ventas_2026.pdf',
          storage_key: `tenants/${workspace.id}/documents/${lastSegment}/reporte_ventas_2026.pdf`,
          content_type: 'application/pdf',
          size_bytes: 1024,
          checksum_sha256: null,
          status: 'READY',
          technical_metadata: { page_count: 5 },
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        };
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ data: doc }),
        });
        return;
      }

      // Catálogo con filtros y búsqueda
      const search = url.searchParams.get('search_term')?.toLowerCase() || '';
      const statusFilter = url.searchParams.get('status');

      let filtered = MOCK_DOCUMENTS;
      if (search) {
        filtered = filtered.filter((d) => d.original_filename.toLowerCase().includes(search));
      }
      if (statusFilter) {
        filtered = filtered.filter((d) => d.status === statusFilter);
      }

      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: filtered,
          pagination: {
            total: filtered.length,
            limit: 25,
            offset: 0,
            has_more: false,
          },
        }),
      });
      return;
    }

    await route.continue();
  });
}
