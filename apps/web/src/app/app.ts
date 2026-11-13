import {
  ChangeDetectionStrategy,
  Component,
  effect,
  inject,
  signal,
  untracked,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

import { AuthService } from './core/auth/auth.service';
import { WorkspaceService } from './core/workspaces/workspace.service';
import { UserMenuComponent } from './layout/user-menu/user-menu';
import { WorkspaceSwitcherComponent } from './layout/workspace-switcher/workspace-switcher';
import { AvatarComponent } from './shared/ui/avatar/avatar';
import { DialogComponent } from './shared/ui/dialog/dialog';
import { IconComponent } from './shared/ui/icon/icon';

/** Shell de la aplicación: barra superior, navegación, drawer móvil y contenido. */
@Component({
  selector: 'app-root',
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    AvatarComponent,
    DialogComponent,
    IconComponent,
    UserMenuComponent,
    WorkspaceSwitcherComponent,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(document:keydown.escape)': 'onEscape()' },
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App {
  readonly authService = inject(AuthService);
  readonly workspaceService = inject(WorkspaceService);
  private readonly router = inject(Router);

  readonly isMobileMenuOpen = signal(false);

  constructor() {
    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe(() => this.closeMobileMenu());

    // Una sola carga de workspaces por sesión, compartida por header, drawer y páginas.
    effect(() => {
      if (this.authService.isAuthenticated()) {
        untracked(() =>
          this.workspaceService.loadWorkspaces().subscribe({ error: () => undefined }),
        );
      }
    });
  }

  toggleMobileMenu(): void {
    this.isMobileMenuOpen.update((open) => !open);
  }

  closeMobileMenu(): void {
    this.isMobileMenuOpen.set(false);
  }

  onEscape(): void {
    this.closeMobileMenu();
  }

  onLogout(): void {
    this.closeMobileMenu();
    this.authService.logout();
    this.workspaceService.setActiveWorkspace(null);
    void this.router.navigate(['/auth/login']);
  }
}
