import {
  HttpClient,
  provideHttpClient,
  withInterceptors,
} from '@angular/common/http';
import {
  HttpTestingController,
  provideHttpClientTesting,
} from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';

import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';

describe('authInterceptor', () => {
  let http: HttpClient;
  let httpTesting: HttpTestingController;
  let authService: AuthService;
  let router: Router;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    });

    http = TestBed.inject(HttpClient);
    httpTesting = TestBed.inject(HttpTestingController);
    authService = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('adjunta cabecera Authorization: Bearer a peticiones de la API de CDM', () => {
    vi.spyOn(authService, 'getAccessToken').mockReturnValue('valid-token-123');

    http.get('/api/v1/workspaces').subscribe();

    const req = httpTesting.expectOne('/api/v1/workspaces');
    expect(req.request.headers.get('Authorization')).toBe(
      'Bearer valid-token-123'
    );
    req.flush({ data: [] });
  });

  it('NO adjunta cabecera Authorization a URLs prefirmadas de S3 o Amazon AWS', () => {
    vi.spyOn(authService, 'getAccessToken').mockReturnValue('valid-token-123');

    const s3Url =
      'https://cdm-bucket.s3.us-east-1.amazonaws.com/tenants/ws-1/doc.pdf?X-Amz-Signature=xyz';
    http.put(s3Url, { data: 'test' }).subscribe();

    const req = httpTesting.expectOne(s3Url);
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
  });

  it('NO adjunta cabecera Authorization a llamadas directas de Cognito', () => {
    vi.spyOn(authService, 'getAccessToken').mockReturnValue('valid-token-123');

    const cognitoUrl = 'https://cognito-idp.us-east-1.amazonaws.com/';
    http.post(cognitoUrl, {}).subscribe();

    const req = httpTesting.expectOne(cognitoUrl);
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
  });

  it('cierra sesión y redirige a login ante error 401 en endpoints de la API', () => {
    vi.spyOn(authService, 'getAccessToken').mockReturnValue('expired-token');
    const logoutSpy = vi.spyOn(authService, 'logout');
    const navigateSpy = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    http.get('/api/v1/workspaces').subscribe({
      error: () => {
        // esperado
      },
    });

    const req = httpTesting.expectOne('/api/v1/workspaces');
    req.flush({ error: 'Unauthorized' }, { status: 401, statusText: 'Unauthorized' });

    expect(logoutSpy).toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalledWith(['/auth/login']);
  });
});
