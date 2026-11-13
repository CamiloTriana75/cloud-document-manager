import { CommonModule } from '@angular/common';
import {
  Component,
  computed,
  DestroyRef,
  HostListener,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet,
} from '@angular/router';
import { filter } from 'rxjs';

import { AuthService } from './core/auth/auth.service';
import { WorkspaceSelectorComponent } from './core/workspaces/workspace-selector';
import { WorkspaceService } from './core/workspaces/workspace.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    WorkspaceSelectorComponent,
  ],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  readonly authService = inject(AuthService);
  readonly workspaceService = inject(WorkspaceService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  readonly isMobileMenuOpen = signal<boolean>(false);

  readonly userInitial = computed(() => {
    const user = this.authService.currentUser();
    const name = user?.name || user?.email || 'U';
    return name.charAt(0).toUpperCase();
  });

  ngOnInit(): void {
    const routerSub = this.router.events
      .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
      .subscribe(() => {
        this.closeMobileMenu();
      });

    this.destroyRef.onDestroy(() => routerSub.unsubscribe());
  }

  toggleMobileMenu(): void {
    this.isMobileMenuOpen.update((open) => !open);
  }

  closeMobileMenu(): void {
    this.isMobileMenuOpen.set(false);
  }

  onLogout(): void {
    this.closeMobileMenu();
    this.authService.logout();
    this.workspaceService.setActiveWorkspace(null);
    this.router.navigate(['/auth/login']);
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    if (this.isMobileMenuOpen()) {
      this.closeMobileMenu();
    }
  }
}
