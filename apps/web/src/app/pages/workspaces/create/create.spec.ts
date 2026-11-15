import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { of, throwError } from 'rxjs';

import { WorkspaceCreateComponent } from './create';
import { WorkspaceService } from '../../../core/workspaces/workspace.service';

describe('WorkspaceCreateComponent', () => {
  let component: WorkspaceCreateComponent;
  let workspaceService: WorkspaceService;
  let router: Router;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [WorkspaceCreateComponent],
      providers: [
        provideHttpClient(),
        provideHttpClientTesting(),
        provideRouter([]),
      ],
    }).compileComponents();

    workspaceService = TestBed.inject(WorkspaceService);
    router = TestBed.inject(Router);
    const fixture = TestBed.createComponent(WorkspaceCreateComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('inicializa con formulario inválido', () => {
    expect(component.form.valid).toBe(false);
  });

  it('autogenera el slug a partir del nombre cuando el slug está vacío', () => {
    component.form.controls.name.setValue('Equipo de Diseño & UX');
    component.onNameChange();

    expect(component.form.controls.slug.value).toBe('equipo-de-diseno-ux');
    expect(component.form.valid).toBe(true);
  });

  it('no envía el formulario si es inválido', () => {
    const spy = vi.spyOn(workspaceService, 'createWorkspace');
    component.onSubmit();
    expect(spy).not.toHaveBeenCalled();
    expect(component.form.controls.name.touched).toBe(true);
  });

  it('llama a createWorkspace y abre el catálogo del nuevo espacio', () => {
    const navigateSpy = vi.spyOn(router, 'navigate').mockResolvedValue(true);
    vi.spyOn(workspaceService, 'createWorkspace').mockReturnValue(
      of({
        id: 'ws-new',
        name: 'Nuevo',
        slug: 'nuevo',
        role: 'OWNER',
        created_at: '',
        updated_at: '',
      })
    );

    component.form.controls.name.setValue('Nuevo');
    component.form.controls.slug.setValue('nuevo');
    component.onSubmit();

    expect(navigateSpy).toHaveBeenCalledWith(['/workspaces', 'ws-new', 'documents']);
    expect(component.isSubmitting()).toBe(false);
  });

  it('muestra mensaje de error cuando falla la creación', () => {
    vi.spyOn(workspaceService, 'createWorkspace').mockReturnValue(
      throwError(() => ({
        error: {
          error: {
            message: 'El slug ya existe.',
          },
        },
      }))
    );

    component.form.controls.name.setValue('Duplicado');
    component.form.controls.slug.setValue('duplicado');
    component.onSubmit();

    expect(component.submitError()).toBe('El slug ya existe.');
    expect(component.isSubmitting()).toBe(false);
  });

  it('muestra la vista previa del identificador mientras se escribe el nombre (CDM-126)', () => {
    const fixture = TestBed.createComponent(WorkspaceCreateComponent);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    const name = el.querySelector('#ws-name') as HTMLInputElement;

    name.value = 'Equipo de Finanzas';
    name.dispatchEvent(new Event('input'));
    fixture.detectChanges();

    expect(el.querySelector('h1')?.textContent).toContain('Crear espacio de trabajo');
    expect(el.querySelector('.slug-preview')?.textContent).toContain('equipo-de-finanzas');
  });
});

