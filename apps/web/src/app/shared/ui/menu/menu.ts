import {
  afterNextRender,
  ChangeDetectionStrategy,
  Component,
  contentChildren,
  Directive,
  ElementRef,
  inject,
  Injector,
  input,
  signal,
  viewChild,
} from '@angular/core';

const SUPPORTS_POPOVER =
  typeof HTMLElement !== 'undefined' && 'showPopover' in HTMLElement.prototype;

let nextMenuId = 0;

/**
 * Ítem de menú proyectado en `app-menu`. Los estilos viven en components.css (`.menu__item`)
 * porque el contenido proyectado no recibe los estilos encapsulados del menú.
 */
@Directive({
  selector: '[appMenuItem]',
  host: {
    class: 'menu__item',
    tabindex: '-1',
    '[attr.role]': 'menuRole()',
    '[attr.aria-checked]': "menuRole() === 'menuitemradio' ? !!menuChecked() : null",
    '(click)': 'onClick()',
  },
})
export class MenuItemDirective {
  readonly menuRole = input<'menuitem' | 'menuitemradio'>('menuitem');
  readonly menuChecked = input<boolean | null>(null);

  readonly element: HTMLElement = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
  private readonly menu = inject(MenuComponent);

  focus(): void {
    this.element.focus();
  }

  protected onClick(): void {
    this.menu.close();
  }
}

/**
 * Menú desplegable accesible (patrón ARIA menu button). En navegadores con Popover API
 * el panel vive en la capa superior (no lo recorta ningún `overflow`); sin ella cae a un
 * panel posicionado bajo el disparador.
 */
@Component({
  selector: 'app-menu',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    '[attr.data-align]': 'align()',
    '(document:click)': 'onDocumentClick($event)',
    '(window:resize)': 'close(false)',
  },
  template: `
    <button
      #trigger
      type="button"
      class="menu__trigger"
      [class]="triggerClass()"
      aria-haspopup="menu"
      [attr.aria-expanded]="open()"
      [attr.aria-controls]="panelId"
      [attr.aria-label]="label()"
      (click)="toggle()"
      (keydown)="onTriggerKeydown($event)"
    >
      <ng-content select="[menuTrigger]" />
    </button>
    <div
      #panel
      class="menu__panel"
      role="menu"
      [id]="panelId"
      [attr.aria-label]="label()"
      [attr.popover]="usePopover ? 'auto' : null"
      [hidden]="!usePopover && !open()"
      (keydown)="onPanelKeydown($event)"
      (toggle)="onToggle($event)"
    >
      <ng-content />
    </div>
  `,
  styles: `
    :host {
      position: relative;
      display: inline-flex;
    }
    .menu__panel {
      min-width: 14rem;
      max-width: min(22rem, calc(100vw - 1.5rem));
      padding: 6px;
      border: 1px solid var(--color-border-strong);
      border-radius: var(--radius-md);
      background: #1a3132;
      color: var(--color-text);
      box-shadow: var(--shadow-popover), var(--inset-highlight);
    }
    .menu__panel:not([popover]) {
      position: absolute;
      top: calc(100% + 6px);
      right: 0;
      z-index: var(--z-popover);
    }
    :host([data-align='start']) .menu__panel:not([popover]) {
      right: auto;
      left: 0;
    }
    .menu__panel[popover] {
      position: fixed;
      inset: auto;
      margin: 0;
    }
  `,
})
export class MenuComponent {
  readonly label = input.required<string>();
  readonly align = input<'start' | 'end'>('end');
  readonly triggerClass = input('btn btn--icon');

  readonly open = signal(false);

  protected readonly usePopover = SUPPORTS_POPOVER;
  protected readonly panelId = `app-menu-${++nextMenuId}`;

  private readonly injector = inject(Injector);
  private readonly host: HTMLElement = inject<ElementRef<HTMLElement>>(ElementRef).nativeElement;
  private readonly trigger = viewChild.required<ElementRef<HTMLButtonElement>>('trigger');
  private readonly panel = viewChild.required<ElementRef<HTMLElement>>('panel');
  private readonly items = contentChildren(MenuItemDirective, { descendants: true });

  toggle(): void {
    if (this.open()) {
      this.close();
    } else {
      this.openMenu(0);
    }
  }

  close(focusTrigger = true): void {
    if (!this.open()) {
      return;
    }
    const panel = this.panel().nativeElement;
    if (this.usePopover && panel.matches(':popover-open')) {
      panel.hidePopover();
    }
    this.open.set(false);
    if (focusTrigger) {
      this.trigger().nativeElement.focus();
    }
  }

  protected onTriggerKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      this.openMenu(event.key === 'ArrowDown' ? 0 : -1);
    }
  }

  protected onPanelKeydown(event: KeyboardEvent): void {
    const items = this.items();
    if (items.length === 0) {
      return;
    }
    const current = items.findIndex((item) => item.element === event.target);
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        this.focusItem((current + 1) % items.length);
        break;
      case 'ArrowUp':
        event.preventDefault();
        this.focusItem((current - 1 + items.length) % items.length);
        break;
      case 'Home':
        event.preventDefault();
        this.focusItem(0);
        break;
      case 'End':
        event.preventDefault();
        this.focusItem(items.length - 1);
        break;
      case 'Escape':
        event.preventDefault();
        event.stopPropagation();
        this.close();
        break;
      case 'Tab':
        this.close(false);
        break;
    }
  }

  protected onToggle(event: Event): void {
    const state = (event as Event & { newState?: string }).newState;
    if (state === 'closed' && this.open()) {
      this.open.set(false);
    }
  }

  protected onDocumentClick(event: MouseEvent): void {
    if (!this.usePopover && this.open() && !this.host.contains(event.target as Node)) {
      this.close(false);
    }
  }

  private openMenu(focusIndex: number): void {
    if (this.open()) {
      return;
    }
    if (this.usePopover) {
      this.positionPanel();
      this.panel().nativeElement.showPopover();
    }
    this.open.set(true);
    afterNextRender(
      () => {
        const count = this.items().length;
        if (count > 0) {
          this.focusItem(focusIndex < 0 ? count - 1 : focusIndex);
        }
      },
      { injector: this.injector },
    );
  }

  private focusItem(index: number): void {
    this.items()[index]?.focus();
  }

  private positionPanel(): void {
    const rect = this.trigger().nativeElement.getBoundingClientRect();
    const style = this.panel().nativeElement.style;
    style.top = `${Math.round(rect.bottom + 6)}px`;
    if (this.align() === 'start') {
      style.left = `${Math.round(rect.left)}px`;
      style.right = 'auto';
    } else {
      style.right = `${Math.round(window.innerWidth - rect.right)}px`;
      style.left = 'auto';
    }
  }
}
