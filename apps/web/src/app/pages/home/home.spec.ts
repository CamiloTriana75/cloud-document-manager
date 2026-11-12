import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { Home } from './home';

describe('Home', () => {
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Home],
      providers: [provideHttpClient(), provideHttpClientTesting()],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('muestra estado operativa cuando la API responde', async () => {
    const fixture = TestBed.createComponent(Home);
    fixture.detectChanges();

    http.expectOne('/health').flush({
      status: 'ok',
      service: 'cdm-api',
      version: '0.1.0',
    });
    fixture.detectChanges();
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.status-ok')).toBeTruthy();
    expect(el.textContent).toContain('Operativa');
    expect(el.textContent).toContain('cdm-api');
  });

  it('muestra error y botón de reintento cuando la API falla', async () => {
    const fixture = TestBed.createComponent(Home);
    fixture.detectChanges();

    http
      .expectOne('/health')
      .flush('no disponible', { status: 503, statusText: 'Service Unavailable' });
    fixture.detectChanges();
    await fixture.whenStable();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.status-error')).toBeTruthy();
    const retry = el.querySelector<HTMLButtonElement>('.btn-retry');
    expect(retry?.textContent).toContain('Reintentar');
  });
});
