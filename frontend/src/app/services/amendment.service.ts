import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { Amendment, AmendmentCreate } from '../models/amendment';

/**
 * Amendments to a published grant_application (FAR 15.206).
 *
 * Routes through `environment.apiGatewayUrl` — the right way. Compare
 * with `grant-application-list.component.ts` which hardcodes :8081 per Item 8.
 */
@Injectable({ providedIn: 'root' })
export class AmendmentService {
  constructor(private http: HttpClient) {}

  list(grant_applicationId: string): Observable<Amendment[]> {
    return this.http.get<Amendment[]>(
      `${environment.apiGatewayUrl}/api/grant-applications/${grant_applicationId}/amendments`,
    );
  }

  issue(grant_applicationId: string, req: AmendmentCreate): Observable<Amendment> {
    return this.http.post<Amendment>(
      `${environment.apiGatewayUrl}/api/grant-applications/${grant_applicationId}/amendments`,
      req,
    );
  }
}
