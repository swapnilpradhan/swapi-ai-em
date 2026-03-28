import { Component, inject, OnInit } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';

import { ApiService, AdminMetrics } from '../../services/api.service';
import { FormatService } from '../../services/format.service';

@Component({
  selector: 'app-admin',
  imports: [MatCardModule, MatButtonModule],
  templateUrl: './admin.html',
  styleUrl: './admin.scss',
})
export class Admin implements OnInit {
  private api = inject(ApiService);
  fmt = inject(FormatService);

  metrics: AdminMetrics | null = null;

  ngOnInit(): void {
    this.refresh();
  }

  refresh() {
    this.api.getAdminMetrics().subscribe({
      next: (m) => (this.metrics = m),
    });
  }
}
