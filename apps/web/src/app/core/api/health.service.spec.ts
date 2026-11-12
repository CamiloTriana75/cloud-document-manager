import { provideHttpClient } from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { HealthService } from './health.service';

describe('HealthService', () => {
  let service: HealthService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(), provideHttpClientTesting()],
    });
    service = TestBed.inject(HealthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('solicita GET /health y devuelve el contrato', () => {
    let result: unknown;
    service.getStatus().subscribe((data) => (result = data));

    const req = http.expectOne('/health');
    expect(req.request.method).toBe('GET');
    req.flush({ status: 'ok', service: 'cdm-api', version: '0.1.0' });

    expect(result).toEqual({
      status: 'ok',
      service: 'cdm-api',
      version: '0.1.0',
    });
  });
});
