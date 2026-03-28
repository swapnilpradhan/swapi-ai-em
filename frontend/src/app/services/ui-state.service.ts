import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class UiStateService {
  isBusy = signal(false);
  busyLabel = signal<string | null>(null);

  setBusy(busy: boolean, label?: string) {
    this.isBusy.set(busy);
    this.busyLabel.set(busy ? (label || 'Working...') : null);
  }
}
