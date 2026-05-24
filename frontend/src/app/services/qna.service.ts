import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { Qna } from '../models/qna';

@Injectable({ providedIn: 'root' })
export class QnaService {
  constructor(private http: HttpClient) {}

  list(grant_applicationId: string): Observable<Qna[]> {
    return this.http.get<Qna[]>(
      `${environment.apiGatewayUrl}/api/grant-applications/${grant_applicationId}/qa`,
    );
  }

  answer(grant_applicationId: string, qaId: string, answer: string): Observable<Qna> {
    return this.http.put<Qna>(
      `${environment.apiGatewayUrl}/api/grant-applications/${grant_applicationId}/qa/${qaId}/answer`,
      { answer },
    );
  }

  submitQuestion(grant_applicationId: string, question: string): Observable<Qna> {
    return this.http.post<Qna>(
      `${environment.apiGatewayUrl}/api/grant-applications/${grant_applicationId}/qa`,
      { question },
    );
  }
}
