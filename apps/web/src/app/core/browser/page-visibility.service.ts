import { DOCUMENT } from '@angular/common';
import { DestroyRef, inject, Injectable, signal } from '@angular/core';

/**
 * Visibilidad de la pestaña como señal: el polling y la escena 3D se pausan
 * cuando el usuario no está mirando la app.
 */
@Injectable({ providedIn: 'root' })
export class PageVisibilityService {
  private readonly document = inject(DOCUMENT);
  private readonly visibleState = signal(this.isVisible());

  readonly visible = this.visibleState.asReadonly();

  constructor() {
    const onChange = () => this.visibleState.set(this.isVisible());
    this.document.addEventListener('visibilitychange', onChange);
    inject(DestroyRef).onDestroy(() =>
      this.document.removeEventListener('visibilitychange', onChange),
    );
  }

  private isVisible(): boolean {
    return this.document.visibilityState !== 'hidden';
  }
}
