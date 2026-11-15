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

import { API_BASE_URL } from '../api/api-config';
import { authInterceptor } from './auth.interceptor';
import { AuthService } from './auth.service';

const API_GATEWAY = 'https://abc123.execute-api.us-east-1.amazonaws.com';

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
        { provide: API_BASE_URL, useValue: API_GATEWAY },
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

  it('adjunta el ID token como Bearer a rutas relativas de la API de CDM', () => {
    vi.spyOn(authService, 'getIdToken').mockReturnValue('id-token-123');

    http.get('/api/v1/workspaces').subscribe();

    const req = httpTesting.expectOne('/api/v1/workspaces');
    expect(req.request.headers.get('Authorization')).toBe('Bearer id-token-123');
    req.flush({ data: [] });
  });

  it('adjunta el token a la API desplegada en API Gateway (*.amazonaws.com) (CDM-133)', () => {
    vi.spyOn(authService, 'getIdToken').mockReturnValue('id-token-123');

    http.get(`${API_GATEWAY}/api/v1/workspaces`).subscribe();

    const req = httpTesting.expectOne(`${API_GATEWAY}/api/v1/workspaces`);
    expect(req.request.headers.get('Authorization')).toBe('Bearer id-token-123');
    req.flush({ data: [] });
  });

  it('NO adjunta cabecera Authorization a URLs prefirmadas de S3', () => {
    vi.spyOn(authService, 'getIdToken').mockReturnValue('id-token-123');

    const s3Url =
      'https://cdm-bucket.s3.us-east-1.amazonaws.com/workspaces/ws-1/doc.pdf?X-Amz-Signature=xyz';
    http.put(s3Url, { data: 'test' }).subscribe();

    const req = httpTesting.expectOne(s3Url);
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
  });

  it('NO adjunta cabecera Authorization a llamadas directas de Cognito', () => {
    vi.spyOn(authService, 'getIdToken').mockReturnValue('id-token-123');

    const cognitoUrl = 'https://cognito-idp.us-east-1.amazonaws.com/';
    http.post(cognitoUrl, {}).subscribe();

    const req = httpTesting.expectOne(cognitoUrl);
    expect(req.request.headers.has('Authorization')).toBe(false);
    req.flush({});
  });

  it('cierra sesión y redirige a login ante error 401 en endpoints de la API', () => {
    vi.spyOn(authService, 'getIdToken').mockReturnValue('expired-token');
    const logoutSpy = vi.spyOn(authService, 'logout');
    const navigateSpy = vi.spyOn(router, 'navigate').mockResolvedValue(true);

    http.get(`${API_GATEWAY}/api/v1/workspaces`).subscribe({
      error: () => {
        // esperado
      },
    });

    const req = httpTesting.expectOne(`${API_GATEWAY}/api/v1/workspaces`);
    req.flush({ error: 'Unauthorized' }, { status: 401, statusText: 'Unauthorized' });

    expect(logoutSpy).toHaveBeenCalled();
    expect(navigateSpy).toHaveBeenCalledWith(['/auth/login']);
  });

  it('un 401 fuera de la API (S3) no cierra la sesión', () => {
    const logoutSpy = vi.spyOn(authService, 'logout');
    const s3Url = 'https://cdm-bucket.s3.us-east-1.amazonaws.com/workspaces/ws-1/doc.pdf?x=1';

    http.put(s3Url, 'x').subscribe({
      error: () => {
        // esperado
      },
    });
    httpTesting.expectOne(s3Url).flush('', { status: 401, statusText: 'Unauthorized' });

    expect(logoutSpy).not.toHaveBeenCalled();
  });
});
