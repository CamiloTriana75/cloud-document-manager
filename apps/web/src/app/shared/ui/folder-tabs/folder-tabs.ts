import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  input,
  output,
  viewChildren,
} from '@angular/core';

export interface FolderTab {
  readonly id: string;
  readonly label: string;
  readonly count: number | null;
}

/**
 * Pestañas-carpeta (patrón ARIA tabs con activación manual: las flechas mueven el foco y
 * Enter/Espacio activan, porque cada cambio dispara una consulta). La carpeta activa se
 * eleva y entra al panel que controla.
 */
@Component({
  selector: 'app-folder-tabs',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="folders" role="tablist" [attr.aria-label]="label()">
      @for (tab of tabs(); track tab.id; let index = $index) {
        <button
          #tabButton
          type="button"
          role="tab"
          class="folder"
          [id]="tabId(tab.id)"
          [attr.aria-selected]="tab.id === active()"
          [attr.aria-controls]="controls()"
          [tabIndex]="tab.id === active() ? 0 : -1"
          (click)="activeChange.emit(tab.id)"
          (keydown)="onKeydown($event, index)"
        >
          <svg class="folder__icon" viewBox="0 0 26 22" aria-hidden="true" focusable="false">
            <path
              class="folder__back"
              d="M1 4.2A3.2 3.2 0 0 1 4.2 1h5.3c.9 0 1.7.4 2.3 1l1.6 1.8c.3.3.7.5 1.1.5h7.3A3.2 3.2 0 0 1 25 7.5v10.3a3.2 3.2 0 0 1-3.2 3.2H4.2A3.2 3.2 0 0 1 1 17.8Z"
            />
            <path
              class="folder__front"
              d="M1 9.2A2.2 2.2 0 0 1 3.2 7h19.6A2.2 2.2 0 0 1 25 9.2v8.6a3.2 3.2 0 0 1-3.2 3.2H4.2A3.2 3.2 0 0 1 1 17.8Z"
            />
          </svg>
          <span class="folder__label">{{ tab.label }}</span>
          @if (tab.count !== null) {
            <span class="folder__count">{{ tab.count }}</span>
          }
        </button>
      }
    </div>
  `,
  styles: `
    :host {
      display: block;
      min-width: 0;
    }
    .folders {
      display: grid;
      grid-auto-flow: column;
      grid-auto-columns: minmax(9.5rem, 1fr);
      align-items: end;
      gap: var(--space-3);
      min-height: 3.75rem;
      overflow-x: auto;
      scrollbar-width: none;
    }
    .folders::-webkit-scrollbar {
      display: none;
    }
    .folder {
      display: flex;
      align-items: center;
      gap: var(--space-3);
      height: 3rem;
      padding: 0 var(--space-4);
      border: 1px solid var(--color-border);
      border-bottom: 0;
      border-radius: var(--radius-md) var(--radius-md) 0 0;
      background: rgba(27, 47, 48, 0.86);
      color: var(--color-text-secondary);
      font-size: var(--text-base);
      text-align: left;
      transition:
        height var(--duration-base) var(--ease-out),
        background-color var(--duration-base) var(--ease-out),
        color var(--duration-fast) var(--ease-out);
    }
    .folder:hover {
      background: rgba(39, 63, 64, 0.92);
      color: var(--color-text);
    }
    .folder:focus-visible {
      outline-offset: -3px;
    }
    .folder[aria-selected='true'] {
      height: 3.75rem;
      border-color: var(--color-border-strong);
      background: rgba(62, 88, 88, 0.94);
      color: var(--color-text);
      box-shadow: var(--inset-highlight);
    }
    .folder__icon {
      flex: none;
      width: 26px;
      height: 22px;
      color: #8f4c34;
      transition:
        color var(--duration-base) var(--ease-out),
        transform var(--duration-base) var(--ease-out);
    }
    .folder__back {
      fill: currentColor;
      opacity: 0.62;
    }
    .folder__front {
      fill: currentColor;
    }
    .folder[aria-selected='true'] .folder__icon {
      color: var(--color-accent);
      transform: translateY(-2px);
    }
    .folder__label {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .folder__count {
      margin-left: auto;
      font-size: var(--text-sm);
      font-variant-numeric: tabular-nums;
      color: var(--color-text-tertiary);
    }
    .folder[aria-selected='true'] .folder__count {
      color: var(--color-text-secondary);
    }
  `,
})
export class FolderTabsComponent {
  readonly tabs = input.required<readonly FolderTab[]>();
  readonly active = input.required<string>();
  /** id del panel que estas pestañas filtran. */
  readonly controls = input.required<string>();
  readonly label = input('Carpetas');

  readonly activeChange = output<string>();

  private readonly tabButtons = viewChildren<ElementRef<HTMLButtonElement>>('tabButton');

  tabId(id: string): string {
    return `folder-tab-${id}`;
  }

  protected onKeydown(event: KeyboardEvent, index: number): void {
    const count = this.tabs().length;
    let target: number | null = null;
    switch (event.key) {
      case 'ArrowRight':
        target = (index + 1) % count;
        break;
      case 'ArrowLeft':
        target = (index - 1 + count) % count;
        break;
      case 'Home':
        target = 0;
        break;
      case 'End':
        target = count - 1;
        break;
    }
    if (target !== null) {
      event.preventDefault();
      this.tabButtons()[target]?.nativeElement.focus();
    }
  }
}
