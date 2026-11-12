import { CommonModule } from '@angular/common';
import { Component, inject, signal } from '@angular/core';
import {
  FormBuilder,
  FormControl,
  FormGroup,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { WorkspaceService } from '../../../core/workspaces/workspace.service';

interface WorkspaceForm {
  name: FormControl<string>;
  slug: FormControl<string>;
}

@Component({
  selector: 'app-workspace-create',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule, RouterLink],
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
      validators: [
        Validators.pattern(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
        Validators.maxLength(100),
      ],
    }),
  });

  readonly isSubmitting = signal<boolean>(false);
  readonly submitError = signal<string | null>(null);

  onNameChange(): void {
    const nameControl = this.form.controls.name;
    const slugControl = this.form.controls.slug;

    // Si el usuario no ha editado manualmente el slug, sugerirlo automáticamente
    if (!slugControl.dirty || !slugControl.value) {
      const slugValue = this.slugify(nameControl.value);
      slugControl.setValue(slugValue);
    }
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
      next: () => {
        this.isSubmitting.set(false);
        this.router.navigate(['/']);
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

  private slugify(text: string): string {
    return text
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9\s-]/g, '')
      .trim()
      .replace(/[\s-]+/g, '-');
  }
}
