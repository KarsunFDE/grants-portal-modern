import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { PeerReview, PeerReviewScore } from '../models/peer_review';

@Injectable({ providedIn: 'root' })
export class PeerReviewService {
  constructor(private http: HttpClient) {}

  get(id: string): Observable<PeerReview> {
    return this.http.get<PeerReview>(
      `${environment.apiGatewayUrl}/api/peer-reviews/${id}`,
    );
  }

  scores(id: string): Observable<PeerReviewScore[]> {
    return this.http.get<PeerReviewScore[]>(
      `${environment.apiGatewayUrl}/api/peer-reviews/${id}/scores`,
    );
  }

  submitScore(id: string, score: Partial<PeerReviewScore>): Observable<PeerReviewScore> {
    return this.http.post<PeerReviewScore>(
      `${environment.apiGatewayUrl}/api/peer-reviews/${id}/scores`,
      score,
    );
  }

  consensus(id: string): Observable<PeerReviewScore[]> {
    return this.http.get<PeerReviewScore[]>(
      `${environment.apiGatewayUrl}/api/peer-reviews/${id}/consensus`,
    );
  }

  /** AI-drafted Source Selection Decision Document narrative (FAR 15.308). */
  draftSsdd(id: string): Observable<{ narrative: string; correlationId: string }> {
    return this.http.post<{ narrative: string; correlationId: string }>(
      `${environment.apiGatewayUrl}/api/ai/eval/ssdd-draft`,
      { peer_reviewId: id },
    );
  }
}
