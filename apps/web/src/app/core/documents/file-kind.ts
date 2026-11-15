import { IconName } from '../../shared/ui/icon/icons';

export type FileKind = 'pdf' | 'image' | 'document' | 'spreadsheet' | 'text' | 'data' | 'other';

/** Familia visual de un tipo MIME (icono y rótulo); no decide permisos ni validación. */
export function fileKind(contentType: string): FileKind {
  const type = contentType.toLowerCase();
  if (type === 'application/pdf') return 'pdf';
  if (type.startsWith('image/')) return 'image';
  if (type.includes('spreadsheetml') || type === 'text/csv') return 'spreadsheet';
  if (type.includes('wordprocessingml')) return 'document';
  if (type === 'application/json') return 'data';
  if (type.startsWith('text/')) return 'text';
  return 'other';
}

export const FILE_KIND_ICON: Readonly<Record<FileKind, IconName>> = {
  pdf: 'file-pdf',
  image: 'image',
  document: 'file-text',
  spreadsheet: 'sheet',
  text: 'file-text',
  data: 'braces',
  other: 'file',
};
