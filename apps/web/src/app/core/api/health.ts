/** Contrato del endpoint de salud (AGENTS.md §11). */
export interface HealthStatus {
  status: string;
  service: string;
  version: string;
}
