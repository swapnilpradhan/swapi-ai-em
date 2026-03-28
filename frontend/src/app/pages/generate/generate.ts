import { Component, inject } from '@angular/core';
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatTableModule } from '@angular/material/table';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { ApiService, GenerationDetail } from '../../services/api.service';
import { FormatService } from '../../services/format.service';
import { UiStateService } from '../../services/ui-state.service';
import { WORKFLOWS } from '../../models/workflow';

@Component({
  selector: 'app-generate',
  imports: [
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatButtonModule,
    MatTableModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './generate.html',
  styleUrl: './generate.scss',
})
export class Generate {
  private api = inject(ApiService);
  private router = inject(Router);
  ui = inject(UiStateService);
  fmt = inject(FormatService);

  workflows = WORKFLOWS;

  form = new FormGroup({
    topic: new FormControl<string>('Chunking and Embedding', {
      nonNullable: true,
      validators: [Validators.required, Validators.maxLength(512)],
    }),
    workflow_type: new FormControl<string>('standard_content_generation', {
      nonNullable: true,
      validators: [Validators.required],
    }),
  });

  generation: GenerationDetail | null = null;
  error: string | null = null;

  stepColumns = ['step', 'agent', 'task', 'status', 'duration'];

  async onGenerate() {
    this.error = null;
    this.generation = null;
    if (this.form.invalid) return;

    const topic = this.form.controls.topic.value.trim();
    const workflow_type = this.form.controls.workflow_type.value;

    this.ui.setBusy(true, 'Generating HTML…');
    this.api.createGeneration({ topic, workflow_type }).subscribe({
      next: (gen) => {
        this.generation = gen;
        this.ui.setBusy(false);
      },
      error: (err) => {
        this.error = err?.error?.detail || err?.message || 'Generation failed';
        this.ui.setBusy(false);
      },
    });
  }

  openPreview() {
    if (!this.generation) return;
    this.router.navigate(['/library', this.generation.id]);
  }
}
