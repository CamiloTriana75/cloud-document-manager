import { DocumentStatus } from './document.models';

/** Tono semántico compartido por chips, barras y visualizaciones. */
export type StatusTone = 'positive' | 'accent' | 'info' | 'warning' | 'danger' | 'neutral';

export interface StatusMeta {
  /** Etiqueta visible en español. */
  readonly label: string;
  readonly tone: StatusTone;
  /** Paso en el pipeline PENDING_UPLOAD (0) → UPLOADED (1) → PROCESSING (2) → final (3). */
  readonly step: 0 | 1 | 2 | 3;
  /** El backend aún está trabajando en el documento: justifica el refresco periódico. */
  readonly inFlight: boolean;
}

/** Fuente única de etiquetas y tonos de estado (AGENTS.md §10). */
export const DOCUMENT_STATUS_META: Readonly<Record<DocumentStatus, StatusMeta>> = {
  PENDING_UPLOAD: { label: 'Pendiente', tone: 'warning', step: 0, inFlight: false },
  UPLOADED: { label: 'Subido', tone: 'info', step: 1, inFlight: true },
  PROCESSING: { label: 'Procesando', tone: 'accent', step: 2, inFlight: true },
  READY: { label: 'Listo', tone: 'positive', step: 3, inFlight: false },
  FAILED: { label: 'Fallido', tone: 'danger', step: 3, inFlight: false },
  DELETED: { label: 'Eliminado', tone: 'neutral', step: 3, inFlight: false },
};

export function isInFlight(status: DocumentStatus): boolean {
  return DOCUMENT_STATUS_META[status].inFlight;
}

export type StatusFilter = 'ALL' | DocumentStatus;

export interface StatusFolder {
  readonly id: StatusFilter;
  readonly label: string;
}

/** Pestañas-carpeta del catálogo; cada una es un filtro exacto que soporta la API. */
export const STATUS_FOLDERS: readonly StatusFolder[] = [
  { id: 'ALL', label: 'Todos' },
  { id: 'READY', label: 'Listos' },
  { id: 'PROCESSING', label: 'Procesando' },
  { id: 'PENDING_UPLOAD', label: 'Pendientes' },
  { id: 'FAILED', label: 'Fallidos' },
];

export interface DocumentTypeOption {
  readonly label: string;
  /** MIME exacto tal como lo guarda el backend (file_policy.py); `null` = sin filtro. */
  readonly value: string | null;
}

/** El backend filtra `content_type` por igualdad: solo MIME exactos, nunca prefijos. */
export const DOCUMENT_TYPE_OPTIONS: readonly DocumentTypeOption[] = [
  { label: 'Todos los tipos', value: null },
  { label: 'PDF', value: 'application/pdf' },
  { label: 'PNG', value: 'image/png' },
  { label: 'JPEG', value: 'image/jpeg' },
  { label: 'Word (DOCX)', value: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' },
  { label: 'Excel (XLSX)', value: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
  { label: 'Texto', value: 'text/plain' },
  { label: 'Markdown', value: 'text/markdown' },
  { label: 'CSV', value: 'text/csv' },
  { label: 'JSON', value: 'application/json' },
];
