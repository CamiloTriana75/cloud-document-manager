import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

/** Iniciales de un nombre o correo ("Ana María" → "AM", "demo.user@x" → "DU"). */
export function initialsOf(name: string): string {
  const base = name.includes('@') ? name.split('@')[0] : name;
  const words = base
    .split(/[\s._-]+/)
    .map((word) => word.trim())
    .filter(Boolean);
  if (words.length === 0) {
    return '?';
  }
  return words
    .slice(0, 2)
    .map((word) => word.charAt(0).toUpperCase())
    .join('');
}

/** Avatar de iniciales; decorativo, el nombre siempre aparece como texto al lado. */
@Component({
  selector: 'app-avatar',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: {
    'aria-hidden': 'true',
    '[style.--avatar-size.px]': 'size()',
  },
  template: `{{ initials() }}`,
  styles: `
    :host {
      display: inline-grid;
      place-items: center;
      flex: none;
      width: var(--avatar-size, 32px);
      height: var(--avatar-size, 32px);
      border: 1px solid var(--color-border-strong);
      border-radius: 50%;
      background:
        radial-gradient(circle at 30% 25%, rgba(255, 255, 255, 0.18), transparent 60%),
        #2f5753;
      color: var(--color-text);
      font-size: calc(var(--avatar-size, 32px) * 0.38);
      font-weight: var(--weight-medium);
      letter-spacing: 0.02em;
      user-select: none;
    }
  `,
})
export class AvatarComponent {
  readonly name = input.required<string>();
  readonly size = input(32);

  protected readonly initials = computed(() => initialsOf(this.name()));
}
