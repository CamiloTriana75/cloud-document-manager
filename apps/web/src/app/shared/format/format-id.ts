/** Prefijo corto y legible de un UUID para tablas y metadatos (el ID completo va en `title`). */
export function shortId(id: string): string {
  return id.slice(0, 8);
}
