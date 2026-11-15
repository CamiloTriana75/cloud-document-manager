import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { afterEach, describe, it } from 'vitest';

import { API_BASE_URL } from './api-config';
import { apiBaseUrlInterceptor } from './api-base-url.interceptor';

const API_GATEWAY = 'https://abc123.execute-api.us-east-1.amazonaws.com';

function setup(baseUrl: string) {
  TestBed.configureTestingModule({
    providers: [
      provideHttpClient(withInterceptors([apiBaseUrlInterceptor])),
      provideHttpClientTesting(),
      { provide: API_BASE_URL, useValue: baseUrl },
    ],
  });
  return {
    http: TestBed.inject(HttpClient),
    httpTesting: TestBed.inject(HttpTestingController),
  };
}

describe('apiBaseUrlInterceptor (CDM-133)', () => {
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('antepone la URL de API Gateway a las rutas /api de CDM', () => {
    const { http, httpTesting } = setup(API_GATEWAY);

    http.get('/api/v1/workspaces').subscribe();

    httpTesting.expectOne(`${API_GATEWAY}/api/v1/workspaces`).flush({ data: [] });
  });

  it('antepone la URL base al health check', () => {
    const { http, httpTesting } = setup(API_GATEWAY);

    http.get('/health').subscribe();

    httpTesting.expectOne(`${API_GATEWAY}/health`).flush({ status: 'ok' });
  });

  it('no modifica URLs absolutas como S3 prefirmado o Cognito', () => {
    const { http, httpTesting } = setup(API_GATEWAY);
    const s3Url = 'https://bucket.s3.us-east-1.amazonaws.com/workspaces/w/doc.pdf?X-Amz-Signature=x';

    http.put(s3Url, 'contenido').subscribe();
    http.post('https://cognito-idp.us-east-1.amazonaws.com/', {}).subscribe();

    httpTesting.expectOne(s3Url).flush({});
    httpTesting.expectOne('https://cognito-idp.us-east-1.amazonaws.com/').flush({});
  });

  it('sin URL base deja la ruta relativa para el proxy del dev-server', () => {
    const { http, httpTesting } = setup('');

    http.get('/api/v1/workspaces').subscribe();

    httpTesting.expectOne('/api/v1/workspaces').flush({ data: [] });
  });
});
