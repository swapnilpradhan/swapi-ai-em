import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTableModule } from '@angular/material/table';

import { ApiService, AuditLog } from '../../services/api.service';
import { FormatService } from '../../services/format.service';

@Component({
  selector: 'app-admin-logs',
  imports: [
    DatePipe,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatTableModule,
  ],
  templateUrl: './admin-logs.html',
  styleUrl: './admin-logs.scss',
})
export class AdminLogs implements OnInit {
  private api = inject(ApiService);
  fmt = inject(FormatService);

  rows: AuditLog[] = [];
  eventType = '';
  agentId = '';
  correlationId = '';
  columns = ['timestamp', 'event_type', 'agent_id', 'correlation_id'];

  ngOnInit(): void {
    this.refresh();
  }

  refresh() {
    this.api
      .listAuditLogs(1, 100, this.eventType || undefined, this.agentId || undefined, this.correlationId || undefined)
      .subscribe({
        next: (res) => (this.rows = res.items),
      });
  }
}
