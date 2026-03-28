import { Component, inject, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatTableModule } from '@angular/material/table';

import { ApiService, GenerationListItem } from '../../services/api.service';
import { FormatService } from '../../services/format.service';

@Component({
  selector: 'app-library',
  imports: [
    DatePipe,
    FormsModule,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
    MatTableModule,
  ],
  templateUrl: './library.html',
  styleUrl: './library.scss',
})
export class Library implements OnInit {
  private api = inject(ApiService);
  fmt = inject(FormatService);

  rows: GenerationListItem[] = [];
  topicFilter = '';
  columns = ['topic', 'status', 'duration', 'created', 'actions'];

  ngOnInit(): void {
    this.refresh();
  }

  refresh() {
    this.api.listGenerations(1, 50, undefined, this.topicFilter || undefined).subscribe({
      next: (res) => (this.rows = res.items),
    });
  }
}
