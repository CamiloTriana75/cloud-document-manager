import { KeyValuePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

import { DOCUMENT_STATUS_META, isInFlight } from '../../../../../core/documents/document-status';
import { DocumentItem } from '../../../../../core/documents/document.models';
import { BytesPipe } from '../../../../../shared/format/bytes.pipe';
import { DateTimePipe } from '../../../../../shared/format/date-time.pipe';
import { IconComponent } from '../../../../../shared/ui/icon/icon';
import { StatusBadgeComponent } from '../../../../../shared/ui/status-badge/status-badge';

const STEPS = ['Sesión de carga', 'Archivo subido', 'Procesamiento', 'Resultado'] as const;

/** Contenido del drawer de detalle: metadatos, línea de tiempo y acciones autorizadas. */
@Component({
  selector: 'app-document-detail',
  imports: [BytesPipe, DateTimePipe, IconComponent, KeyValuePipe, StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <article class="detail">
      <header class="detail__header">
        <div class="detail__heading">
          <app-status-badge [status]="document().status" />
          <h2 id="detail-title" class="detail__title">{{ document().original_filename }}</h2>
        </div>
        <button type="button" class="btn btn--icon" aria-label="Cerrar detalle" (click)="closed.emit()">
          <app-icon name="x" [size]="18" />
        </button>
      </header>

      @if (document().status === 'FAILED') {
        <p class="notice notice--danger" role="alert">
          <app-icon name="alert-circle" [size]="16" />
          {{ document().failure_reason || 'El procesamiento falló de forma no recuperable.' }}
        </p>
      } @else if (inFlight()) {
        <p class="notice" role="status">
          <span class="progress-dots" aria-hidden="true"><span></span><span></span><span></span></span>
          Procesando de forma asíncrona. La descarga se habilita cuando esté listo.
        </p>
      }

      <ol class="timeline" aria-label="Avance del procesamiento">
        @for (step of steps; track step; let index = $index) {
          <li
            class="timeline__step"
            [class.is-done]="index < reached() && !(index === 3 && document().status === 'FAILED')"
            [class.is-current]="index === reached() - 1 && inFlight()"
            [class.is-failed]="index === 3 && document().status === 'FAILED'"
          >
            <span class="timeline__dot" aria-hidden="true"></span>
            {{ index === 3 ? resultLabel() : step }}
          </li>
        }
      </ol>

      <dl class="facts">
        <div class="fact"><dt>ID de documento</dt><dd class="mono">{{ document().id }}</dd></div>
        <div class="fact">
          <dt>Tamaño</dt>
          <dd>{{ document().size_bytes | bytes }} ({{ document().size_bytes }} bytes)</dd>
        </div>
        <div class="fact"><dt>Tipo MIME</dt><dd class="mono">{{ document().content_type }}</dd></div>
        <div class="fact"><dt>Fecha de carga</dt><dd>{{ document().created_at | dateTime }}</dd></div>
        <div class="fact"><dt>Última actualización</dt><dd>{{ document().updated_at | dateTime }}</dd></div>
        @if (document().storage_key) {
          <div class="fact">
            <dt>Clave de almacenamiento S3</dt>
            <dd class="mono fact__wrap">{{ document().storage_key }}</dd>
          </div>
        }
        @if (document().retry_count) {
          <div class="fact"><dt>Reintentos</dt><dd>{{ document().retry_count }} / 3</dd></div>
        }
      </dl>

      @if ((document().technical_metadata | keyvalue).length > 0) {
        <section class="metadata" aria-labelledby="metadata-title">
          <h3 id="metadata-title" class="metadata__title">Metadatos Técnicos (JSONB)</h3>
          <dl class="metadata__list">
            @for (entry of document().technical_metadata | keyvalue; track entry.key) {
              <div class="metadata__row">
                <dt>{{ entry.key }}</dt>
                <dd class="mono">{{ format(entry.value) }}</dd>
              </div>
            }
          </dl>
        </section>
      }

      <footer class="detail__actions">
        @if (document().status === 'READY') {
          <button type="button" class="btn btn--primary" [disabled]="busy()" (click)="download.emit(document())">
            <app-icon name="download" [size]="16" />
            Descargar archivo
          </button>
        }
        @if (document().status === 'FAILED' && canRetry()) {
          <button type="button" class="btn btn--secondary" [disabled]="busy()" (click)="retry.emit(document())">
            <app-icon name="retry" [size]="16" />
            Reintentar procesamiento
          </button>
        }
        @if (canDelete()) {
          <button type="button" class="btn btn--ghost detail__delete" (click)="remove.emit(document())">
            <app-icon name="trash" [size]="16" />
            Eliminar documento
          </button>
        }
      </footer>
    </article>
  `,
  styles: `
    :host {
      display: block;
    }
    .detail {
      display: grid;
      gap: var(--space-6);
      padding: var(--space-6);
    }
    .detail__header {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: var(--space-4);
    }
    .detail__heading {
      display: grid;
      gap: var(--space-3);
      min-width: 0;
    }
    .detail__title {
      font-size: var(--text-2xl);
      font-weight: var(--weight-light);
      line-height: var(--leading-tight);
      letter-spacing: var(--tracking-display);
      overflow-wrap: anywhere;
    }
    .notice {
      display: flex;
      align-items: center;
      gap: var(--space-3);
      padding: var(--space-3) var(--space-4);
      border-radius: var(--radius-md);
      background: var(--color-accent-soft);
      color: var(--color-text);
      font-size: var(--text-md);
    }
    .notice--danger {
      background: var(--color-danger-soft);
    }
    .notice--danger app-icon {
      color: var(--color-danger);
    }
    .timeline {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: var(--space-2);
      margin: 0;
      padding: 0;
      list-style: none;
      font-size: var(--text-xs);
      color: var(--color-text-tertiary);
    }
    .timeline__step {
      display: grid;
      gap: var(--space-2);
    }
    .timeline__dot {
      height: 4px;
      border-radius: var(--radius-pill);
      background: var(--color-track);
    }
    .is-done {
      color: var(--color-text-secondary);
    }
    .is-done .timeline__dot {
      background: var(--color-positive);
    }
    .is-current .timeline__dot {
      background: var(--color-accent);
    }
    .is-failed .timeline__dot {
      background: var(--color-danger);
    }
    .facts,
    .metadata__list {
      display: grid;
      gap: var(--space-3);
      margin: 0;
    }
    .fact,
    .metadata__row {
      display: grid;
      grid-template-columns: 11rem minmax(0, 1fr);
      gap: var(--space-4);
      font-size: var(--text-md);
    }
    .fact dt,
    .metadata__row dt {
      color: var(--color-text-tertiary);
    }
    .fact dd,
    .metadata__row dd {
      margin: 0;
      overflow-wrap: anywhere;
    }
    .metadata {
      display: grid;
      gap: var(--space-3);
      padding-top: var(--space-5);
      border-top: 1px solid var(--color-border);
    }
    .metadata__title {
      font-size: var(--text-base);
      font-weight: var(--weight-regular);
    }
    .detail__actions {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-3);
      padding-top: var(--space-5);
      border-top: 1px solid var(--color-border);
    }
    .detail__delete {
      margin-left: auto;
      color: var(--color-danger);
    }
    @media (max-width: 520px) {
      .fact,
      .metadata__row {
        grid-template-columns: 1fr;
        gap: var(--space-1);
      }
    }
  `,
})
export class DocumentDetailComponent {
  readonly document = input.required<DocumentItem>();
  readonly canDelete = input(false);
  readonly canRetry = input(false);
  readonly busy = input(false);

  readonly closed = output<void>();
  readonly download = output<DocumentItem>();
  readonly retry = output<DocumentItem>();
  readonly remove = output<DocumentItem>();

  protected readonly steps = STEPS;
  protected readonly inFlight = computed(() => isInFlight(this.document().status));
  /** Pasos alcanzados: Pendiente 1 · Subido 2 · Procesando 3 · Listo/Fallido 4. */
  protected readonly reached = computed(() => DOCUMENT_STATUS_META[this.document().status].step + 1);
  protected readonly resultLabel = computed(() => {
    const status = this.document().status;
    return status === 'READY' || status === 'FAILED' ? DOCUMENT_STATUS_META[status].label : 'Resultado';
  });

  protected format(value: unknown): string {
    return typeof value === 'object' && value !== null ? JSON.stringify(value) : String(value);
  }
}
