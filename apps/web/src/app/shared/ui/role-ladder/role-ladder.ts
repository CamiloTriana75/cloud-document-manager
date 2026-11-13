import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { ROLE_ORDER, roleLevel } from '../../../core/workspaces/workspace-roles';
import { WorkspaceRole } from '../../../core/workspaces/workspace.models';

/** Escalera de rol (VIEWER → OWNER): muestra el nivel del usuario en el workspace activo. */
@Component({
  selector: 'app-role-ladder',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="ladder__head">
      <span class="ladder__caption">Tu rol</span>
      <span class="ladder__role">{{ role() }}</span>
    </div>
    <div class="ladder__steps" role="img" [attr.aria-label]="ariaLabel()">
      @for (step of steps; track step; let index = $index) {
        <span
          class="ladder__step"
          [class.is-filled]="index < level()"
          [class.is-current]="index === level() - 1"
        ></span>
      }
    </div>
  `,
  styles: `
    :host {
      display: grid;
      gap: var(--space-2);
      min-width: 13rem;
    }
    .ladder__head {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: var(--space-4);
      font-size: var(--text-sm);
    }
    .ladder__caption {
      color: var(--color-text-tertiary);
    }
    .ladder__role {
      font-size: var(--text-base);
      color: var(--color-text);
    }
    .ladder__steps {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 4px;
    }
    .ladder__step {
      height: 4px;
      border-radius: var(--radius-pill);
      background: var(--color-track);
      transition: background-color var(--duration-base) var(--ease-out);
    }
    .ladder__step.is-filled {
      background: rgba(255, 255, 255, 0.34);
    }
    .ladder__step.is-current {
      background: var(--color-accent);
    }
  `,
})
export class RoleLadderComponent {
  readonly role = input.required<WorkspaceRole>();

  protected readonly steps = ROLE_ORDER;
  protected readonly level = computed(() => roleLevel(this.role()));
  protected readonly ariaLabel = computed(
    () => `Rol ${this.role()}, nivel ${this.level()} de ${ROLE_ORDER.length}`,
  );
}
