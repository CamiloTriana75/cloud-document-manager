/**
 * Modelos de dominio y contratos HTTP de Documentos y Carga en Angular (CDM-31).
 */

export type DocumentStatus =
  | 'PENDING_UPLOAD'
  | 'UPLOADED'
  | 'PROCESSING'
  | 'READY'
  | 'FAILED'
  | 'DELETED';

export interface DocumentItem {
  id: string;
  workspace_id: string;
  uploaded_by: string;
  original_filename: string;
  storage_key: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256?: string | null;
  status: DocumentStatus;
  technical_metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface UploadSessionRequest {
  original_filename: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256?: string | null;
}

export interface UploadSessionResponse {
  upload_session_id: string;
  document_id: string;
  upload_url: string;
  storage_key: string;
  expires_in_seconds: number;
  required_headers: Record<string, string>;
}

export interface DownloadUrlResponse {
  document_id: string;
  original_filename: string;
  download_url: string;
  expires_in_seconds: number;
}

export type UploadPhase =
  | 'idle'
  | 'requesting'
  | 'uploading'
  | 'completing'
  | 'completed'
  | 'error'
  | 'cancelled';

export interface UploadProgressState {
  status: UploadPhase;
  progressPercentage: number;
  loadedBytes: number;
  totalBytes: number;
  error?: string | null;
  document?: DocumentItem | null;
}

export const ALLOWED_UPLOAD_EXTENSIONS = [
  '.pdf',
  '.png',
  '.jpg',
  '.jpeg',
  '.txt',
  '.md',
  '.csv',
  '.json',
  '.docx',
  '.xlsx',
];

export const MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB
