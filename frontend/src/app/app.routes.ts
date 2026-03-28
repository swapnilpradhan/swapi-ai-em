import { Routes } from '@angular/router';

import { Generate } from './pages/generate/generate';
import { Library } from './pages/library/library';
import { Preview } from './pages/preview/preview';
import { Admin } from './pages/admin/admin';
import { AdminLogs } from './pages/admin-logs/admin-logs';
import { AdminMessages } from './pages/admin-messages/admin-messages';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'generate' },
  { path: 'generate', component: Generate },
  { path: 'library', component: Library },
  { path: 'library/:id', component: Preview },
  { path: 'admin', component: Admin },
  { path: 'admin/logs', component: AdminLogs },
  { path: 'admin/messages', component: AdminMessages },
  { path: '**', redirectTo: 'generate' },
];
