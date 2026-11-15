import { DocumentItem, DocumentStatus } from '../../../../core/documents/document.models';

/** Documentos de prueba compartidos por las specs del dashboard. */
export function testDocument(
  id: string,
  status: DocumentStatus,
  overrides: Partial<DocumentItem> = {},
): DocumentItem {
  return {
    id,
    workspace_id: 'ws-1',
    uploaded_by: 'u-1',
    original_filename: `${id}.pdf`,
    storage_key: `tenants/ws-1/documents/${id}`,
    content_type: 'application/pdf',
    size_bytes: 1536,
    status,
    technical_metadata: { paginas: 5 },
    created_at: '2026-11-10T10:00:00Z',
    updated_at: '2026-11-10T10:05:00Z',
    failure_reason: null,
    ...overrides,
  };
}
