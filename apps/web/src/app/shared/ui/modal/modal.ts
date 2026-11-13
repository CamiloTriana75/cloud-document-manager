import { CommonModule } from '@angular/common';
import { Component, HostListener, input, output } from '@angular/core';

@Component({
  selector: 'app-modal',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (isOpen()) {
      <div
        class="modal-backdrop"
        role="dialog"
        aria-modal="true"
        [attr.aria-label]="title()"
      >
        <button
          type="button"
          class="modal-scrim"
          (click)="onClose()"
          aria-label="Cerrar diálogo modal"
        ></button>
        <div class="modal-dialog">
          @if (title()) {
            <header class="modal-header">
              <h2 class="modal-title">{{ title() }}</h2>
              <button
                type="button"
                class="modal-close-btn"
                (click)="onClose()"
                aria-label="Cerrar modal"
              >
                ✕
              </button>
            </header>
          }
          <div class="modal-body">
            <ng-content />
          </div>
          <footer class="modal-footer">
            <ng-content select="[modal-footer]" />
          </footer>
        </div>
      </div>
    }
  `,
  styles: [
    `
      .modal-backdrop {
        position: fixed;
        inset: 0;
        z-index: 50;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: var(--space-4);
      }
      .modal-scrim {
        position: fixed;
        inset: 0;
        background-color: rgba(15, 23, 42, 0.45);
        backdrop-filter: blur(1.5px);
        border: none;
        cursor: pointer;
        z-index: 1;
      }
      .modal-dialog {
        position: relative;
        z-index: 2;
        background: var(--color-surface);
        border-radius: var(--radius-md);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1),
          0 8px 10px -6px rgba(0, 0, 0, 0.1);
        width: 100%;
        max-width: 540px;
        max-height: 90vh;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
        animation: modal-enter 0.15s ease-out;
      }
      @keyframes modal-enter {
        from {
          opacity: 0;
          transform: scale(0.97);
        }
        to {
          opacity: 1;
          transform: scale(1);
        }
      }
      .modal-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: var(--space-4) var(--space-6);
        border-bottom: 1px solid var(--color-border);
      }
      .modal-title {
        margin: 0;
        font-size: var(--font-size-lg);
        font-weight: var(--font-weight-semibold);
        color: var(--color-text);
      }
      .modal-close-btn {
        background: transparent;
        border: none;
        font-size: 1.125rem;
        cursor: pointer;
        color: var(--color-text-secondary);
        padding: 4px;
        border-radius: var(--radius-sm);
      }
      .modal-close-btn:hover {
        background-color: #f1f5f9;
        color: var(--color-text);
      }
      .modal-body {
        padding: var(--space-6);
        color: var(--color-text);
        font-size: var(--font-size-md);
      }
      .modal-footer {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        gap: var(--space-3);
        padding: var(--space-4) var(--space-6);
        border-top: 1px solid var(--color-border);
        background-color: #f8fafc;
      }
    `,
  ],
})
export class ModalComponent {
  readonly isOpen = input<boolean>(false);
  readonly title = input<string>('');
  readonly modalClose = output<void>();

  onClose(): void {
    this.modalClose.emit();
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.isOpen()) {
      this.onClose();
    }
  }
}
