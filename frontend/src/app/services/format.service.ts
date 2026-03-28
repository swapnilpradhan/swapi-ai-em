import { Injectable } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class FormatService {
  ms(ms?: number | null): string {
    if (ms === null || ms === undefined) return '-';
    if (ms < 1000) return `${ms.toFixed(0)} ms`;
    const s = ms / 1000;
    if (s < 60) return `${s.toFixed(1)} s`;
    const m = Math.floor(s / 60);
    const rem = s % 60;
    return `${m}m ${rem.toFixed(0)}s`;
  }

  isoToLocal(iso?: string | null): string {
    if (!iso) return '-';
    const d = new Date(iso);
    return d.toLocaleString();
  }
}
