import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface GenerationListItem {
  id: string;
  topic: string;
  workflow_type: string;
  status: string;
  total_duration_ms?: number | null;
  created_at: string;
}

export interface GenerationStep {
  id: string;
  step_number: number;
  agent_id: string;
  task_type: string;
  status: string;
  duration_ms?: number | null;
  error?: string | null;
  result_summary?: any;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface GenerationDetail {
  id: string;
  topic: string;
  workflow_type: string;
  status: string;
  file_path?: string | null;
  total_duration_ms?: number | null;
  error?: string | null;
  created_at: string;
  updated_at: string;
  steps: GenerationStep[];
}

export interface GenerateRequest {
  topic: string;
  workflow_type: string;
}

export interface AdminMetrics {
  total_generations: number;
  completed_generations: number;
  failed_generations: number;
  success_rate: number;
  avg_duration_ms: number | null;
  total_a2a_messages: number;
  total_audit_events: number;
  agent_stats: Record<string, any>;
}

export interface AuditLog {
  id: string;
  event_type: string;
  agent_id?: string | null;
  correlation_id?: string | null;
  payload?: any;
  timestamp: string;
}

export interface A2AMessage {
  id: string;
  message_id: string;
  sender: string;
  receiver: string;
  message_type: string;
  priority?: number | null;
  content?: any;
  correlation_id?: string | null;
  response_time_ms?: number | null;
  timestamp: string;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private base = '/api';

  constructor(private http: HttpClient) {}

  createGeneration(req: GenerateRequest): Observable<GenerationDetail> {
    return this.http.post<GenerationDetail>(`${this.base}/generations`, req);
  }

  listGenerations(page = 1, pageSize = 20, status?: string, topic?: string): Observable<PaginatedResponse<GenerationListItem>> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (status) params = params.set('status', status);
    if (topic) params = params.set('topic', topic);
    return this.http.get<PaginatedResponse<GenerationListItem>>(`${this.base}/generations`, { params });
  }

  getGeneration(id: string): Observable<GenerationDetail> {
    return this.http.get<GenerationDetail>(`${this.base}/generations/${id}`);
  }

  getGenerationSteps(id: string): Observable<GenerationStep[]> {
    return this.http.get<GenerationStep[]>(`${this.base}/generations/${id}/steps`);
  }

  getGenerationHtmlUrl(id: string): string {
    return `${this.base}/generations/${id}/html`;
  }

  getAdminMetrics(): Observable<AdminMetrics> {
    return this.http.get<AdminMetrics>(`${this.base}/admin/metrics`);
  }

  listAuditLogs(page = 1, pageSize = 50, eventType?: string, agentId?: string, correlationId?: string): Observable<PaginatedResponse<AuditLog>> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (eventType) params = params.set('event_type', eventType);
    if (agentId) params = params.set('agent_id', agentId);
    if (correlationId) params = params.set('correlation_id', correlationId);
    return this.http.get<PaginatedResponse<AuditLog>>(`${this.base}/admin/audit-logs`, { params });
  }

  listMessages(page = 1, pageSize = 50, sender?: string, receiver?: string, messageType?: string, correlationId?: string): Observable<PaginatedResponse<A2AMessage>> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (sender) params = params.set('sender', sender);
    if (receiver) params = params.set('receiver', receiver);
    if (messageType) params = params.set('message_type', messageType);
    if (correlationId) params = params.set('correlation_id', correlationId);
    return this.http.get<PaginatedResponse<A2AMessage>>(`${this.base}/admin/messages`, { params });
  }
}
