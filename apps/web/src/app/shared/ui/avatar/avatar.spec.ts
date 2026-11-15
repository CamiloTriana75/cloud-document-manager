import { TestBed } from '@angular/core/testing';
import { describe, expect, it } from 'vitest';

import { AvatarComponent, initialsOf } from './avatar';

describe('initialsOf', () => {
  it('toma las iniciales de las dos primeras palabras', () => {
    expect(initialsOf('Ana María Pérez')).toBe('AM');
    expect(initialsOf('demo.user')).toBe('DU');
  });

  it('usa la parte local de un correo', () => {
    expect(initialsOf('tester@cdm.example.com')).toBe('T');
  });

  it('devuelve un signo cuando no hay nombre', () => {
    expect(initialsOf('   ')).toBe('?');
  });
});

describe('AvatarComponent', () => {
  it('muestra las iniciales y es decorativo', () => {
    const fixture = TestBed.createComponent(AvatarComponent);
    fixture.componentRef.setInput('name', 'Camilo Triana');
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;

    expect(el.textContent?.trim()).toBe('CT');
    expect(el.getAttribute('aria-hidden')).toBe('true');
  });
});
