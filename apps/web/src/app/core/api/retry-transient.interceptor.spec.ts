import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API_BASE_URL } from './api-config';
import { retryTransientInterceptor } from './retry-transient.interceptor';

const API = 'https://abc123.execute-api.us-east-1.amazonaws.com';
const URL = `${API}/api/v1/workspaces`;

describe('retryTransientInterceptor (CDM-133)', () => {
  let http: HttpClient;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    vi.useFakeTimers();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([retryTransientInterceptor])),
        provideHttpClientTesting(),
        { provide: API_BASE_URL, useValue: API },
      ],
    });
    http = TestBed.inject(HttpClient);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
    vi.useRealTimers();
  });

  it('reintenta un GET de la API ante 503 (throttling de Lambda) y entrega la respuesta', () => {
    let body: unknown;
    http.get(URL).subscribe((value) => (body = value));

    httpTesting.expectOne(URL).flush('', { status: 503, statusText: 'Service Unavailable' });
    vi.advanceTimersByTime(1_000);
    httpTesting.expectOne(URL).flush({ data: [] });

    expect(body).toEqual({ data: [] });
  });

  it('se rinde tras dos reintentos y propaga el error', () => {
    let status = 0;
    http.get(URL).subscribe({ error: (err) => (status = err.status) });

    for (let attempt = 0; attempt < 3; attempt++) {
      httpTesting.expectOne(URL).flush('', { status: 503, statusText: 'Service Unavailable' });
      vi.advanceTimersByTime(5_000);
    }

    expect(status).toBe(503);
  });

  it('no reintenta escrituras (POST) para no duplicar efectos', () => {
    let status = 0;
    http.post(URL, { name: 'x' }).subscribe({ error: (err) => (status = err.status) });

    httpTesting.expectOne(URL).flush('', { status: 503, statusText: 'Service Unavailable' });
    vi.advanceTimersByTime(5_000);

    expect(status).toBe(503);
  });

  it('no reintenta errores definitivos ni peticiones fuera de la API', () => {
    http.get(URL).subscribe({ error: () => undefined });
    httpTesting.expectOne(URL).flush('', { status: 404, statusText: 'Not Found' });

    const s3 = 'https://bucket.s3.us-east-1.amazonaws.com/workspaces/w/doc.pdf?X-Amz-Signature=x';
    http.get(s3).subscribe({ error: () => undefined });
    httpTesting.expectOne(s3).flush('', { status: 503, statusText: 'Slow Down' });

    vi.advanceTimersByTime(5_000);
  });
});
