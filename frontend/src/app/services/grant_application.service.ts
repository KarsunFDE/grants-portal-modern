import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { GrantApplication, GrantApplicationCreate } from '../models/grant_application';

/**
 * GrantApplication service — the "right" way to talk to the backend.
 *
 * Goes through the API gateway (environment.apiGatewayUrl). The cohort
 * compares this with `grant-application-list.component.ts`, which hardcodes
 * `http://localhost:8081` and bypasses the gateway (Item 8).
 */
@Injectable({ providedIn: 'root' })
export class GrantApplicationService {
  private readonly baseUrl = `${environment.apiGatewayUrl}/api/grant-applications`;

  constructor(private http: HttpClient) {}

  list(): Observable<GrantApplication[]> {
    return this.http.get<GrantApplication[]>(this.baseUrl);
  }

  get(id: string): Observable<GrantApplication> {
    return this.http.get<GrantApplication>(`${this.baseUrl}/${id}`);
  }

  create(req: GrantApplicationCreate): Observable<GrantApplication> {
    return this.http.post<GrantApplication>(this.baseUrl, req);
  }
}
