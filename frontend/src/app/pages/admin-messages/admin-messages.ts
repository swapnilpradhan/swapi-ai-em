import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTableModule } from '@angular/material/table';

import { ApiService, A2AMessage } from '../../services/api.service';

@Component({
  selector: 'app-admin-messages',
  imports: [
    DatePipe,
    FormsModule,
    MatCardModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatTableModule,
  ],
  templateUrl: './admin-messages.html',
  styleUrl: './admin-messages.scss',
})
export class AdminMessages implements OnInit {
  private api = inject(ApiService);

  rows: A2AMessage[] = [];
  sender = '';
  receiver = '';
  messageType = '';
  correlationId = '';
  columns = ['timestamp', 'sender', 'receiver', 'message_type', 'correlation_id'];

  ngOnInit(): void {
    this.refresh();
  }

  refresh() {
    this.api
      .listMessages(1, 100, this.sender || undefined, this.receiver || undefined, this.messageType || undefined, this.correlationId || undefined)
      .subscribe({
        next: (res) => (this.rows = res.items),
      });
  }
}
