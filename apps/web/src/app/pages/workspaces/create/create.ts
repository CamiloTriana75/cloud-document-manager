import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import {
  FormBuilder,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { WorkspaceService } from '../../../core/workspaces/workspace.service';
import { AlertComponent } from '../../../shared/ui/alert/alert';
import { CoilSceneComponent } from '../../../shared/ui/coil-scene/coil-scene';
import { IconComponent } from '../../../shared/ui/icon/icon';

interface WorkspaceForm {
  name: FormControl<string>;
  slug: FormControl<string>;
}

/** Alta de un workspace; quien lo crea queda como OWNER y entra directamente a su catálogo. */
@Component({
  selector: 'app-workspace-create',
  imports: [ReactiveFormsModule, RouterLink, AlertComponent, CoilSceneComponent, IconComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './create.html',
  styleUrl: './create.css',
})
export class WorkspaceCreateComponent {
  private readonly fb = inject(FormBuilder);
  readonly workspaceService = inject(WorkspaceService);
  private readonly router = inject(Router);

  readonly form: FormGroup<WorkspaceForm> = this.fb.group<WorkspaceForm>({
    name: this.fb.control('', {
      nonNullable: true,
      validators: [Validators.required, Validators.minLength(1), Validators.maxLength(100)],
    }),
    slug: this.fb.control('', {
      nonNullable: true,
      validators: [Validators.pattern(/^[a-z0-9]+(?:-[a-z0-9]+)*$/), Validators.maxLength(100)],
    }),
  });

  readonly isSubmitting = signal<boolean>(false);
  readonly submitError = signal<string | null>(null);
  protected readonly slugPreview = signal('');

  onNameChange(): void {
    const slugControl = this.form.controls.slug;
    // Mientras el usuario no edite el slug a mano, se sugiere a partir del nombre.
    if (!slugControl.dirty || !slugControl.value) {
      slugControl.setValue(this.slugify(this.form.controls.name.value));
    }
    this.slugPreview.set(slugControl.value);
  }

  onSlugChange(): void {
    this.slugPreview.set(this.form.controls.slug.value);
  }

  onSubmit(): void {
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.isSubmitting.set(true);
    this.submitError.set(null);

    const raw = this.form.getRawValue();
    const payload = {
      name: raw.name.trim(),
      slug: raw.slug.trim() ? raw.slug.trim() : undefined,
    };

    this.workspaceService.createWorkspace(payload).subscribe({
      next: (workspace) => {
        this.isSubmitting.set(false);
        void this.router.navigate(['/workspaces', workspace.id, 'documents']);
      },
      error: (err) => {
        this.isSubmitting.set(false);
        const msg =
          err?.error?.error?.message ||
          'No se pudo crear el espacio de trabajo. Revisa los datos e intenta nuevamente.';
        this.submitError.set(msg);
      },
    });
  }

  protected invalid(control: 'name' | 'slug'): boolean {
    const field = this.form.controls[control];
    return field.invalid && field.touched;
  }

  private slugify(text: string): string {
    return text
      .toLowerCase()
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-z0-9\s-]/g, '')
      .trim()
      .replace(/[\s-]+/g, '-');
  }
}
