import { ChangeDetectionStrategy, Component, input, output, signal } from '@angular/core';

import { FILE_KIND_ICON, fileKind } from '../../../../../core/documents/file-kind';
import { ALLOWED_UPLOAD_EXTENSIONS, DocumentItem } from '../../../../../core/documents/document.models';
import { UploadQueueItem } from '../../../../../core/documents/upload-queue.service';
import { RelativeTimePipe } from '../../../../../shared/format/relative-time.pipe';
import { IconComponent } from '../../../../../shared/ui/icon/icon';
import { IconName } from '../../../../../shared/ui/icon/icons';
import { StatusBadgeComponent } from '../../../../../shared/ui/status-badge/status-badge';

/**
 * Panel de Actividad: últimos documentos del workspace con su estado en el pipeline,
 * cargas en curso y una barra para soltar archivos (solo si el rol puede subir).
 */
@Component({
  selector: 'app-activity-panel',
  imports: [IconComponent, RelativeTimePipe, StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="activity surface-card" aria-labelledby="activity-title">
      <header class="card-header">
        <h2 id="activity-title" class="section-title">Actividad</h2>
        <span class="live"><span class="live__dot" aria-hidden="true"></span>En vivo</span>
      </header>

      <ol class="feed" role="list" aria-live="polite">
        @for (upload of uploads(); track upload.id) {
          <li class="feed__item">
            <span class="feed__icon feed__icon--upload"><app-icon name="upload-cloud" [size]="18" /></span>
            <div class="feed__body">
              <span class="feed__name">{{ upload.file.name }}</span>
              <div
                class="progress"
                role="progressbar"
                aria-valuemin="0"
                aria-valuemax="100"
                [attr.aria-valuenow]="upload.progress"
                [attr.aria-label]="'Subiendo ' + upload.file.name"
              >
                <span class="progress__fill" [style.width.%]="upload.progress"></span>
              </div>
            </div>
          </li>
        }
        @for (doc of recent(); track doc.id) {
          <li class="feed__item">
            <span class="feed__icon"><app-icon [name]="icon(doc)" [size]="18" /></span>
            <div class="feed__body">
              <button type="button" class="feed__name feed__link" (click)="openDocument.emit(doc)">
                {{ doc.original_filename }}
              </button>
              <span class="feed__meta">
                <app-status-badge [status]="doc.status" />
                <span class="feed__time">{{ doc.updated_at | relativeTime }}</span>
              </span>
              @if (doc.status === 'FAILED' && doc.failure_reason) {
                <span class="feed__reason">{{ doc.failure_reason }}</span>
              }
            </div>
          </li>
        } @empty {
          @if (uploads().length === 0) {
            <li class="feed__empty">Sin actividad todavía. Los documentos nuevos aparecerán aquí.</li>
          }
        }
      </ol>

      @if (canUpload()) {
        <div
          class="dropbar"
          [class.is-dragging]="dragging()"
          (dragover)="onDragOver($event)"
          (dragleave)="dragging.set(false)"
          (drop)="onDrop($event)"
        >
          <app-icon name="upload-cloud" [size]="18" />
          <span class="dropbar__text">Suelta archivos aquí para subirlos</span>
          <button
            type="button"
            class="btn btn--icon btn--primary"
            aria-label="Seleccionar archivos para subir"
            (click)="fileInput.click()"
          >
            <app-icon name="arrow-up" [size]="18" />
          </button>
          <input
            #fileInput
            type="file"
            multiple
            hidden
            [accept]="accept"
            (change)="onPick($event)"
          />
        </div>
      }
    </section>
  `,
  styles: `
    :host {
      display: block;
      min-width: 0;
    }
    .activity {
      display: flex;
      flex-direction: column;
      height: 100%;
      min-height: 24rem;
    }
    .live {
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      font-size: var(--text-sm);
      color: var(--color-text-tertiary);
    }
    .live__dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--color-positive);
      animation: live 2s var(--ease-in-out) infinite;
    }
    @keyframes live {
      50% {
        opacity: 0.35;
      }
    }
    .feed {
      display: grid;
      flex: 1;
      align-content: start;
      gap: var(--space-1);
      margin: 0;
      padding: 0 var(--space-3) var(--space-3);
      list-style: none;
      overflow-y: auto;
      max-height: 34rem;
    }
    .feed__item {
      display: flex;
      gap: var(--space-3);
      padding: var(--space-3) var(--space-2);
      border-radius: var(--radius-sm);
    }
    .feed__item:hover {
      background: rgba(255, 255, 255, 0.03);
    }
    .feed__icon {
      display: grid;
      flex: none;
      place-items: center;
      width: 2.25rem;
      height: 2.25rem;
      border-radius: 50%;
      background: var(--color-neutral-soft);
      color: var(--color-text-secondary);
    }
    .feed__icon--upload {
      background: var(--color-accent-soft);
      color: var(--color-accent-text);
    }
    .feed__body {
      display: grid;
      flex: 1;
      gap: var(--space-1);
      min-width: 0;
    }
    .feed__name {
      overflow: hidden;
      color: var(--color-text);
      font-size: var(--text-md);
      text-align: left;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .feed__link {
      padding: 0;
      border: 0;
      background: none;
      cursor: pointer;
    }
    .feed__link:hover {
      text-decoration: underline;
      text-underline-offset: 0.2em;
    }
    .feed__meta {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: var(--space-2) var(--space-3);
      font-size: var(--text-sm);
    }
    .feed__time {
      color: var(--color-text-tertiary);
    }
    .feed__reason {
      font-size: var(--text-xs);
      color: var(--color-danger);
    }
    .feed__empty {
      padding: var(--space-6) var(--space-2);
      color: var(--color-text-tertiary);
    }
    .dropbar {
      display: flex;
      align-items: center;
      gap: var(--space-3);
      margin: 0 var(--space-4) var(--space-4);
      padding: var(--space-2) var(--space-2) var(--space-2) var(--space-4);
      border: 1px dashed var(--color-border-strong);
      border-radius: var(--radius-pill);
      background: var(--color-field);
      color: var(--color-text-tertiary);
      transition:
        border-color var(--duration-fast) var(--ease-out),
        background-color var(--duration-fast) var(--ease-out);
    }
    .dropbar.is-dragging {
      border-color: var(--color-accent);
      background: var(--color-accent-soft);
      color: var(--color-text);
    }
    .dropbar__text {
      flex: 1;
      font-size: var(--text-md);
    }
  `,
})
export class ActivityPanelComponent {
  readonly recent = input.required<readonly DocumentItem[]>();
  readonly uploads = input<readonly UploadQueueItem[]>([]);
  readonly canUpload = input(false);

  readonly filesDropped = output<File[]>();
  readonly openDocument = output<DocumentItem>();

  protected readonly dragging = signal(false);
  protected readonly accept = ALLOWED_UPLOAD_EXTENSIONS.join(',');

  protected icon(doc: DocumentItem): IconName {
    return FILE_KIND_ICON[fileKind(doc.content_type)];
  }

  protected onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(true);
  }

  protected onDrop(event: DragEvent): void {
    event.preventDefault();
    this.dragging.set(false);
    const files = Array.from(event.dataTransfer?.files ?? []);
    if (files.length > 0) {
      this.filesDropped.emit(files);
    }
  }

  protected onPick(event: Event): void {
    const input = event.target as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    if (files.length > 0) {
      this.filesDropped.emit(files);
    }
    input.value = '';
  }
}
