import { ChangeDetectionStrategy, Component, input, output } from '@angular/core';

import { FILE_KIND_ICON, fileKind } from '../../../../../core/documents/file-kind';
import { DocumentItem } from '../../../../../core/documents/document.models';
import { BytesPipe } from '../../../../../shared/format/bytes.pipe';
import { DateTimePipe } from '../../../../../shared/format/date-time.pipe';
import { shortId } from '../../../../../shared/format/format-id';
import { IconComponent } from '../../../../../shared/ui/icon/icon';
import { IconName } from '../../../../../shared/ui/icon/icons';
import { StatusBadgeComponent } from '../../../../../shared/ui/status-badge/status-badge';
import { CatalogSort, SortColumn } from '../../catalog.store';

interface SortableHeader {
  readonly column: SortColumn;
  readonly label: string;
}

const HEADERS: readonly SortableHeader[] = [
  { column: 'original_filename', label: 'Nombre' },
  { column: 'created_at', label: 'Fecha' },
  { column: 'size_bytes', label: 'Tamaño' },
  { column: 'status', label: 'Estado' },
];

/** Tabla del catálogo: presentación pura, las acciones salen como eventos. */
@Component({
  selector: 'app-document-table',
  imports: [BytesPipe, DateTimePipe, IconComponent, StatusBadgeComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="table-scroll">
      <table class="data-table" aria-label="Lista de documentos del espacio">
        <thead>
          <tr>
            <th scope="col">ID</th>
            @for (header of headers; track header.column) {
              <th scope="col" [attr.aria-sort]="ariaSort(header.column)">
                <button type="button" class="th-sort" (click)="sortChange.emit(header.column)">
                  {{ header.label }}
                  <app-icon [name]="sortIcon(header.column)" [size]="14" />
                </button>
              </th>
            }
            <th scope="col"><span class="sr-only">Acciones</span></th>
          </tr>
        </thead>
        <tbody>
          @for (doc of documents(); track doc.id) {
            <tr [class.is-failed]="doc.status === 'FAILED'">
              <td class="cell-id mono" [title]="doc.id">{{ shortId(doc.id) }}</td>
              <td class="cell-name">
                <span class="file">
                  <span class="file__icon"><app-icon [name]="icon(doc)" [size]="18" /></span>
                  <span class="file__text">
                    <span class="file__name" [title]="doc.original_filename">{{ doc.original_filename }}</span>
                    @if (doc.status === 'FAILED' && doc.failure_reason) {
                      <span class="file__reason">{{ doc.failure_reason }}</span>
                    } @else {
                      <span class="file__type">{{ doc.content_type }}</span>
                    }
                  </span>
                </span>
              </td>
              <td class="cell-date">{{ doc.created_at | dateTime }}</td>
              <td class="cell-size tabular">{{ doc.size_bytes | bytes }}</td>
              <td><app-status-badge [status]="doc.status" /></td>
              <td class="cell-actions">
                <div class="actions">
                  @if (doc.status === 'READY') {
                    <button
                      type="button"
                      class="btn btn--icon btn--sm"
                      aria-label="Descargar archivo"
                      title="Descargar archivo"
                      [disabled]="busyId() === doc.id"
                      (click)="download.emit(doc)"
                    >
                      <app-icon name="download" [size]="16" />
                    </button>
                  }
                  @if (doc.status === 'FAILED' && canRetry()) {
                    <button
                      type="button"
                      class="btn btn--icon btn--sm"
                      aria-label="Reintentar procesamiento"
                      title="Reintentar procesamiento"
                      [disabled]="busyId() === doc.id"
                      (click)="retry.emit(doc)"
                    >
                      <app-icon name="retry" [size]="16" />
                    </button>
                  }
                  @if (canDelete()) {
                    <button
                      type="button"
                      class="btn btn--icon btn--sm action-danger"
                      aria-label="Eliminar documento"
                      title="Eliminar documento"
                      (click)="remove.emit(doc)"
                    >
                      <app-icon name="trash" [size]="16" />
                    </button>
                  }
                  <button
                    type="button"
                    class="btn btn--icon btn--sm"
                    aria-label="Ver detalle técnico del documento"
                    title="Ver detalle"
                    (click)="openDetail.emit(doc)"
                  >
                    <app-icon name="more-horizontal" [size]="16" />
                  </button>
                </div>
              </td>
            </tr>
          }
        </tbody>
      </table>
    </div>
  `,
  styles: `
    :host {
      display: block;
    }
    .data-table td {
      height: 3.5rem;
    }
    .cell-id {
      width: 6.5rem;
      color: var(--color-text-tertiary);
    }
    .cell-name {
      min-width: 15rem;
      max-width: 26rem;
    }
    .cell-date,
    .cell-size {
      color: var(--color-text-secondary);
      white-space: nowrap;
    }
    .file {
      display: flex;
      align-items: center;
      gap: var(--space-3);
      min-width: 0;
    }
    .file__icon {
      display: grid;
      flex: none;
      place-items: center;
      width: 2.25rem;
      height: 2.25rem;
      border-radius: var(--radius-sm);
      background: var(--color-neutral-soft);
      color: var(--color-text-secondary);
    }
    .file__text {
      display: grid;
      min-width: 0;
    }
    .file__name {
      overflow: hidden;
      color: var(--color-text);
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .file__type,
    .file__reason {
      overflow: hidden;
      font-size: var(--text-xs);
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .file__type {
      color: var(--color-text-tertiary);
    }
    .file__reason {
      color: var(--color-danger);
    }
    .is-failed .file__icon {
      background: var(--color-danger-soft);
      color: var(--color-danger);
    }
    .cell-actions {
      width: 1%;
    }
    .actions {
      display: flex;
      justify-content: flex-end;
      gap: var(--space-1);
    }
    .action-danger:hover {
      background: var(--color-danger-soft);
      color: var(--color-danger);
    }
  `,
})
export class DocumentTableComponent {
  readonly documents = input.required<readonly DocumentItem[]>();
  readonly sort = input.required<CatalogSort>();
  readonly canDelete = input(false);
  readonly canRetry = input(false);
  readonly busyId = input<string | null>(null);

  readonly sortChange = output<SortColumn>();
  readonly openDetail = output<DocumentItem>();
  readonly download = output<DocumentItem>();
  readonly retry = output<DocumentItem>();
  readonly remove = output<DocumentItem>();

  protected readonly headers = HEADERS;
  protected readonly shortId = shortId;

  protected icon(doc: DocumentItem): IconName {
    return FILE_KIND_ICON[fileKind(doc.content_type)];
  }

  protected ariaSort(column: SortColumn): 'ascending' | 'descending' | 'none' {
    const sort = this.sort();
    if (sort.column !== column) {
      return 'none';
    }
    return sort.direction === 'asc' ? 'ascending' : 'descending';
  }

  protected sortIcon(column: SortColumn): IconName {
    const sort = this.sort();
    if (sort.column !== column) {
      return 'chevrons-up-down';
    }
    return sort.direction === 'asc' ? 'arrow-up' : 'arrow-down';
  }
}
