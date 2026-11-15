import { ChangeDetectionStrategy, Component } from '@angular/core';

import { CoilSceneComponent } from '../../../shared/ui/coil-scene/coil-scene';
import { IconComponent } from '../../../shared/ui/icon/icon';

/**
 * Layout dividido de autenticación: panel visual con la escena 3D y el formulario proyectado.
 * No crea `<main>`: el shell ya lo provee.
 */
@Component({
  selector: 'app-auth-layout',
  imports: [CoilSceneComponent, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="auth">
      <section class="auth__visual">
        <app-coil-scene class="auth__scene" />
        <div class="auth__statement">
          <p class="auth__claim">Documentos en la nube, aislados por equipo.</p>
          <ul class="auth__assurances" role="list">
            <li><app-icon name="lock" [size]="16" /> Almacenamiento privado en S3</li>
            <li><app-icon name="shield-check" [size]="16" /> Permisos por rol en cada espacio</li>
            <li><app-icon name="layers" [size]="16" /> Procesamiento asíncrono con estados visibles</li>
          </ul>
        </div>
      </section>
      <div class="auth__form">
        <div class="auth__card surface-card"><ng-content /></div>
      </div>
    </div>
  `,
  styles: `
    :host {
      display: block;
    }
    .auth {
      display: grid;
      grid-template-columns: minmax(0, 1.1fr) minmax(0, 1fr);
      align-items: center;
      gap: var(--space-10);
      max-width: var(--layout-max);
      min-height: calc(100dvh - var(--header-height));
      margin-inline: auto;
      padding: var(--space-6) var(--layout-gutter) var(--space-12);
    }
    .auth__visual {
      position: relative;
      isolation: isolate;
      display: grid;
      align-content: end;
      min-height: 34rem;
      overflow-x: clip;
    }
    .auth__scene {
      position: absolute;
      inset: 0 -2rem 4rem;
      z-index: -1;
    }
    .auth__statement {
      display: grid;
      gap: var(--space-5);
      padding-bottom: var(--space-4);
    }
    .auth__claim {
      max-width: 16ch;
      font-size: clamp(2rem, 3.4vw, 3rem);
      font-weight: var(--weight-light);
      line-height: var(--leading-tight);
      letter-spacing: var(--tracking-display);
      text-shadow: 0 2px 28px rgba(9, 22, 23, 0.8);
    }
    .auth__assurances {
      display: grid;
      gap: var(--space-2);
      margin: 0;
      padding: 0;
      list-style: none;
      color: var(--color-text-secondary);
    }
    .auth__assurances li {
      display: flex;
      align-items: center;
      gap: var(--space-2);
    }
    .auth__assurances app-icon {
      color: var(--color-accent-text);
    }
    .auth__form {
      display: grid;
      justify-items: center;
    }
    .auth__card {
      display: grid;
      gap: var(--space-5);
      width: 100%;
      max-width: 27rem;
      padding: var(--space-8);
    }
    @media (max-width: 900px) {
      .auth {
        grid-template-columns: minmax(0, 1fr);
        min-height: auto;
        gap: var(--space-6);
      }
      .auth__visual {
        min-height: 14rem;
      }
      .auth__scene {
        inset: -2rem -4rem 0;
        opacity: 0.6;
      }
      .auth__assurances {
        display: none;
      }
      .auth__card {
        padding: var(--space-6);
      }
    }
  `,
})
export class AuthLayoutComponent {}
