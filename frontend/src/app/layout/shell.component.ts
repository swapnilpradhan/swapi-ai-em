import { Component, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { UiStateService } from '../services/ui-state.service';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatToolbarModule,
    MatSidenavModule,
    MatListModule,
    MatIconModule,
    MatButtonModule,
  ],
  template: `
  <mat-sidenav-container class="shell">
    <mat-sidenav mode="side" opened class="sidenav">
      <div class="brand">
        <div class="title">SWAPI AI-EM</div>
        <div class="subtitle">Generate • Preview • Audit</div>
      </div>

      <mat-nav-list>
        <a mat-list-item routerLink="/generate" routerLinkActive="active">
          <mat-icon>bolt</mat-icon>
          <span>Generate</span>
        </a>
        <a mat-list-item routerLink="/library" routerLinkActive="active">
          <mat-icon>folder</mat-icon>
          <span>Library</span>
        </a>
        <a mat-list-item routerLink="/admin" routerLinkActive="active">
          <mat-icon>admin_panel_settings</mat-icon>
          <span>Admin</span>
        </a>
        <a mat-list-item routerLink="/admin/logs" routerLinkActive="active">
          <mat-icon>receipt_long</mat-icon>
          <span>Audit Logs</span>
        </a>
        <a mat-list-item routerLink="/admin/messages" routerLinkActive="active">
          <mat-icon>forum</mat-icon>
          <span>A2A Messages</span>
        </a>
      </mat-nav-list>
    </mat-sidenav>

    <mat-sidenav-content>
      <mat-toolbar color="primary" class="toolbar">
        <span class="spacer"></span>
        @if (ui.isBusy()) {
          <span class="busy">{{ ui.busyLabel() }}</span>
        }
      </mat-toolbar>

      <div class="content">
        <router-outlet />
      </div>
    </mat-sidenav-content>
  </mat-sidenav-container>
  `,
  styles: [`
    .shell { height: 100vh; }
    .sidenav { width: 260px; padding: 0; }
    .brand { padding: 16px 16px 8px; border-bottom: 1px solid rgba(0,0,0,.08); }
    .title { font-weight: 700; letter-spacing: .5px; }
    .subtitle { font-size: 12px; opacity: .7; margin-top: 4px; }
    .toolbar { position: sticky; top: 0; z-index: 2; }
    .content { padding: 20px; max-width: 1200px; margin: 0 auto; }
    .spacer { flex: 1; }
    .busy { font-size: 13px; opacity: .85; }
    a.active { background: rgba(0,0,0,.06); }
  `],
})
export class ShellComponent {
  ui = inject(UiStateService);
}
