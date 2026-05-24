import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-peer-review-panel',
  standalone: true,
  imports: [CommonModule],
  template: `
    <h2>PeerReview panels</h2>
    <p>
      <em>
        Stub view. PeerReview panel UI is part of W3 cohort work — multi-agent
        coordination + HITL interrupt nodes.
      </em>
    </p>
    <button (click)="createPanel()">Create stub peer_review panel</button>
    <pre *ngIf="result">{{ result | json }}</pre>
    <p *ngIf="error" style="color: crimson">{{ error }}</p>
  `,
})
export class PeerReviewPanelComponent {
  result: unknown = null;
  error: string | null = null;

  constructor(private http: HttpClient) {}

  createPanel(): void {
    this.error = null;
    this.http
      .post(`${environment.apiGatewayUrl}/api/peer-reviews`, {
        grant_applicationId: 'stub-grant_application-id',
      })
      .subscribe({
        next: (r) => (this.result = r),
        error: (e) => (this.error = `Failed: ${e.message ?? e}`),
      });
  }
}
