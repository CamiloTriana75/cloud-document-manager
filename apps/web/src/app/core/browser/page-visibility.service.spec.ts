import { DOCUMENT } from '@angular/common';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, expect, it } from 'vitest';

import { PageVisibilityService } from './page-visibility.service';

function setVisibility(state: DocumentVisibilityState): void {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state });
  document.dispatchEvent(new Event('visibilitychange'));
}

describe('PageVisibilityService', () => {
  afterEach(() => setVisibility('visible'));

  it('refleja la visibilidad de la pestaña', () => {
    TestBed.configureTestingModule({ providers: [{ provide: DOCUMENT, useValue: document }] });
    const service = TestBed.inject(PageVisibilityService);

    expect(service.visible()).toBe(true);

    setVisibility('hidden');
    expect(service.visible()).toBe(false);

    setVisibility('visible');
    expect(service.visible()).toBe(true);
  });
});
