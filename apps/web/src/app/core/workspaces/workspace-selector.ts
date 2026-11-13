import { CommonModule } from '@angular/common';
import { Component, ElementRef, HostListener, inject, OnInit, signal } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from '../auth/auth.service';
import { Workspace } from './workspace.models';
import { WorkspaceService } from './workspace.service';

@Component({
  selector: 'app-workspace-selector',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './workspace-selector.html',
  styleUrl: './workspace-selector.css',
})
export class WorkspaceSelectorComponent implements OnInit {
  readonly workspaceService = inject(WorkspaceService);
  readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  private readonly elementRef = inject(ElementRef);

  readonly isOpen = signal<boolean>(false);

  ngOnInit(): void {
    if (this.authService.isAuthenticated()) {
      this.workspaceService.loadWorkspaces().subscribe({
        error: () => {
          // Capturado por el servicio
        },
      });
    }
  }

  toggleDropdown(): void {
    this.isOpen.update((v) => !v);
  }

  closeDropdown(): void {
    this.isOpen.set(false);
  }

  selectWorkspace(workspace: Workspace): void {
    this.workspaceService.setActiveWorkspace(workspace);
    this.closeDropdown();

    const currentUrl = this.router.url;
    if (currentUrl.includes('/workspaces/')) {
      if (currentUrl.includes('/members')) {
        this.router.navigate(['/workspaces', workspace.id, 'members']);
      } else if (currentUrl.includes('/upload')) {
        this.router.navigate(['/workspaces', workspace.id, 'upload']);
      } else {
        this.router.navigate(['/workspaces', workspace.id, 'documents']);
      }
    }
  }

  navigateToNewWorkspace(): void {
    this.closeDropdown();
    this.router.navigate(['/workspaces/new']);
  }

  navigateToMembers(): void {
    const active = this.workspaceService.activeWorkspace();
    if (active) {
      this.closeDropdown();
      this.router.navigate(['/workspaces', active.id, 'members']);
    }
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: MouseEvent): void {
    if (!this.elementRef.nativeElement.contains(event.target)) {
      this.closeDropdown();
    }
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.closeDropdown();
  }
}
