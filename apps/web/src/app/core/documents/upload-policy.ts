import { ALLOWED_UPLOAD_EXTENSIONS, MAX_UPLOAD_SIZE_BYTES } from './document.models';

/**
 * Validación previa en el navegador (UX). El backend vuelve a validar tipo, tamaño
 * y contenido real; esto solo evita esperas inútiles.
 *
 * @returns mensaje de error en español, o `null` si el archivo puede subirse.
 */
export function validateUploadFile(file: Pick<File, 'name' | 'size'>): string | null {
  const allowed = ALLOWED_UPLOAD_EXTENSIONS.join(', ');
  const dot = file.name.lastIndexOf('.');
  if (dot <= 0 || dot === file.name.length - 1) {
    return `El archivo no tiene extensión. Formatos admitidos: ${allowed}.`;
  }
  const extension = file.name.slice(dot).toLowerCase();
  if (!ALLOWED_UPLOAD_EXTENSIONS.includes(extension)) {
    return `El formato "${extension}" no está permitido. Formatos admitidos: ${allowed}.`;
  }
  if (file.size <= 0) {
    return 'El archivo seleccionado está vacío (0 bytes).';
  }
  if (file.size > MAX_UPLOAD_SIZE_BYTES) {
    const maxMb = Math.round(MAX_UPLOAD_SIZE_BYTES / (1024 * 1024));
    return `El archivo supera el tamaño máximo permitido de ${maxMb} MB.`;
  }
  return null;
}
