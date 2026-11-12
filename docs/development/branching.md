# Estrategia de ramificación — CDM

- **Fecha:** 2026-11-12
- **Jira:** CDM-1 (acuerdo de trabajo)
- **Estado:** Aceptado por el propietario (2026-11-12)

## Modelo: 3 niveles, ramas por incremento (no por tarea)

```
main ──────●───────────────●──────►  estable, releases taggeados (v0.x)
             \           /
develop ──●───●──●──●─────►          integración continua
              \     \
feat/inc1-… ───●─────►                rama por incremento/épica
```

| Rama | Propósito | Reglas |
|---|---|---|
| `main` | Estable, demostrable, releases (`v0.1.0`, …) | Solo merges desde `develop`. Protegida. No commits directos. |
| `develop` | Integración del trabajo en curso | Base de todas las ramas de trabajo. Docs pequeñas y fixes menores pueden commitearse directo. |
| `feat/<incremento>` | Una rama por incremento/épica (ej. `feat/inc1-identity-workspaces`) | Vida media (días–semanas). Se crea desde `develop` y vuelve a `develop` vía PR. |

## Reglas

1. **Una rama por incremento o épica, no por tarea Jira.** Varias tareas CDM-XX conviven en la misma rama; el issue se referencia en el mensaje de commit.
2. Commits con convención: `feat(scope): …`, `fix(scope): …`, `docs(scope): …`, `test(scope): …`, `refactor(scope): …` + referencia Jira (`(CDM-12)`).
3. PR de rama de incremento → `develop` cuando el incremento (o un hito parcial coherente) está listo: pruebas en verde, lint/type-check limpios.
4. Merge `develop` → `main` solo cuando existe algo demostrable y Probado; se etiqueta `vX.Y.Z`.
5. Fix crítico en producción: rama puntual `fix/…` desde `main`, merge a `main` y a `develop`.
6. Nunca commitear secretos, state de Terraform ni artefactos generados.
7. CI (GitHub Actions) corre en PRs hacia `develop` y en `main`.

## Mapeo con incrementos

| Incremento | Rama |
|---|---|
| 0 — repo, CI, entorno local | `feat/inc0-foundation` |
| 1 — identidad, workspaces, permisos | `feat/inc1-identity-workspaces` |
| 2 — carga segura y S3 | `feat/inc2-secure-upload` |
| 3 — async y catálogo | `feat/inc3-async-catalog` |
| 4 — UI y endurecimiento | `feat/inc4-ui-hardening` |
| 5 — release | `feat/inc5-release` |
