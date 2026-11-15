import { DOCUMENT } from '@angular/common';
import {
  afterRenderEffect,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  inject,
  input,
  output,
  viewChild,
} from '@angular/core';

/**
 * Diálogo modal o drawer lateral sobre `<dialog>` nativo: capa superior, fondo inerte
 * y trampa de foco del navegador. El padre controla `open`; Escape y clic en el fondo
 * emiten `closed` para que el padre decida. Al cerrar devuelve el foco a quien lo abrió.
 */
@Component({
  selector: 'app-dialog',
  changeDetection: ChangeDetectionStrategy.OnPush,
  // El clic en el fondo llega por burbujeo al host; su equivalente de teclado es Escape (cancel).
  host: { '(click)': 'onDialogClick($event)' },
  template: `
    <dialog
      #dialog
      class="dialog"
      [attr.data-variant]="variant()"
      [attr.aria-label]="label()"
      [attr.aria-labelledby]="labelledBy()"
      (cancel)="onCancel($event)"
    >
      <div class="dialog__surface"><ng-content /></div>
    </dialog>
  `,
  styles: `
    :host {
      display: contents;
    }
    .dialog {
      width: 100%;
      max-width: min(34rem, calc(100vw - 2rem));
      max-height: calc(100dvh - 2rem);
      padding: 0;
      border: 0;
      background: transparent;
      color: var(--color-text);
      overflow: visible;
    }
    .dialog::backdrop {
      background: var(--color-scrim);
      backdrop-filter: blur(4px);
    }
    .dialog[open] {
      animation: dialog-in var(--duration-base) var(--ease-out);
    }
    .dialog__surface {
      max-height: inherit;
      overflow: auto;
      border: 1px solid var(--color-border-strong);
      border-radius: var(--radius-lg);
      background: var(--color-panel);
      box-shadow: var(--shadow-popover), var(--inset-highlight);
    }
    .dialog[data-variant='drawer'] {
      height: 100dvh;
      max-height: 100dvh;
      max-width: min(32rem, 100vw);
      margin: 0 0 0 auto;
    }
    .dialog[data-variant='drawer'][open] {
      animation-name: drawer-in;
    }
    .dialog[data-variant='drawer'] .dialog__surface {
      height: 100%;
      border-radius: var(--radius-xl) 0 0 var(--radius-xl);
      border-right: 0;
    }
    @keyframes dialog-in {
      from {
        opacity: 0;
        transform: translateY(8px) scale(0.98);
      }
    }
    @keyframes drawer-in {
      from {
        opacity: 0.4;
        transform: translateX(24px);
      }
    }
  `,
})
export class DialogComponent {
  readonly open = input(false);
  readonly variant = input<'modal' | 'drawer'>('modal');
  readonly label = input<string | null>(null);
  readonly labelledBy = input<string | null>(null);

  readonly closed = output<void>();

  private readonly document = inject(DOCUMENT);
  private readonly dialogRef = viewChild.required<ElementRef<HTMLDialogElement>>('dialog');
  private returnFocus: HTMLElement | null = null;

  constructor() {
    afterRenderEffect(() => {
      const dialog = this.dialogRef().nativeElement;
      if (this.open()) {
        this.show(dialog);
      } else {
        this.hide(dialog);
      }
    });
  }

  protected onCancel(event: Event): void {
    event.preventDefault();
    this.closed.emit();
  }

  protected onDialogClick(event: MouseEvent): void {
    // El contenido vive en .dialog__surface; un clic con target en el <dialog> es el fondo.
    if (event.target === this.dialogRef().nativeElement) {
      this.closed.emit();
    }
  }

  private show(dialog: HTMLDialogElement): void {
    if (dialog.hasAttribute('open')) {
      return;
    }
    this.returnFocus = this.document.activeElement as HTMLElement | null;
    if (typeof dialog.showModal === 'function') {
      dialog.showModal();
    } else {
      dialog.setAttribute('open', '');
    }
  }

  private hide(dialog: HTMLDialogElement): void {
    if (!dialog.hasAttribute('open')) {
      return;
    }
    if (typeof dialog.close === 'function') {
      dialog.close();
    } else {
      dialog.removeAttribute('open');
    }
    const target = this.returnFocus;
    this.returnFocus = null;
    if (target && this.document.contains(target)) {
      target.focus();
    }
  }
}
