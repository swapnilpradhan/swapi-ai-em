import { Component, inject, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { DomSanitizer, SafeResourceUrl } from '@angular/platform-browser';

import { ApiService, GenerationDetail, GenerationStep } from '../../services/api.service';
import { FormatService } from '../../services/format.service';

@Component({
  selector: 'app-preview',
  imports: [DatePipe, MatCardModule, MatTableModule, MatButtonModule],
  templateUrl: './preview.html',
  styleUrl: './preview.scss',
})
export class Preview implements OnInit {
  private route = inject(ActivatedRoute);
  private api = inject(ApiService);
  private sanitizer = inject(DomSanitizer);
  fmt = inject(FormatService);

  gen: GenerationDetail | null = null;
  iframeUrl: SafeResourceUrl | null = null;
  error: string | null = null;

  columns = ['step', 'agent', 'task', 'status', 'duration'];

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) {
      this.error = 'Missing generation id';
      return;
    }
    this.iframeUrl = this.sanitizer.bypassSecurityTrustResourceUrl(this.api.getGenerationHtmlUrl(id));
    this.api.getGeneration(id).subscribe({
      next: (g) => (this.gen = g),
      error: (err) => (this.error = err?.error?.detail || 'Failed to load generation'),
    });
  }

  stepRows(): GenerationStep[] {
    return this.gen?.steps || [];
  }
}
