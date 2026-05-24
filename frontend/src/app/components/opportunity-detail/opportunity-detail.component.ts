import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { GrantApplication } from '../../models/grant_application';
import { Amendment } from '../../models/amendment';
import { Qna } from '../../models/qna';
import { FIXTURE_SOLICITATIONS, FIXTURE_AMENDMENTS, FIXTURE_QNA } from '../../services/mock-fixtures';

/**
 * Public-facing Opportunity Detail.
 *
 * Renders Sections A–M, amendments timeline, public Q&A history.
 * The description renders raw (Item 9) — a teaching surface for
 * W4 Wed AI Security (prompt-injection-via-stored-content).
 */
@Component({
  selector: 'app-opportunity-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>{{ grant_application?.title }}</h2>
        <div class="subtitle">
          {{ grant_application?.noticeType }} · {{ grant_application?.agencyId }} · NAICS {{ grant_application?.naics }}
        </div>
      </div>
      <a routerLink="/public/opportunities"><button class="secondary">← All opportunities</button></a>
    </div>

    <div class="two-col">
      <div>
        <div class="card">
          <h3>Description</h3>
          <!-- ⚠ Item 9: description rendered raw via innerHTML in the production
               version. Here we use text interpolation but the backend stores
               raw HTML; cohort discovers the W4 surface in the network tab. -->
          <p>{{ grant_application?.description }}</p>
        </div>

        <div class="card">
          <h3>Section C — Statement of Work</h3>
          <pre style="white-space:pre-wrap;font-family:inherit">{{ sectionC() }}</pre>
        </div>

        <div class="card">
          <h3>Section L — Instructions to Offerors</h3>
          <pre style="white-space:pre-wrap;font-family:inherit">{{ sectionL() }}</pre>
        </div>

        <div class="card">
          <h3>Section M — PeerReview Factors</h3>
          <pre style="white-space:pre-wrap;font-family:inherit">{{ sectionM() }}</pre>
        </div>
      </div>

      <div>
        <div class="card">
          <h3>Key dates</h3>
          <table>
            <tbody>
              <tr><th>Posted</th><td>{{ grant_application?.createdAt | date:'mediumDate' }}</td></tr>
              <tr><th>Proposals due</th><td>{{ grant_application?.proposalsDueAt ? (grant_application?.proposalsDueAt | date:'medium') : '—' }}</td></tr>
              <tr><th>Status</th><td><span class="badge" [ngClass]="(grant_application?.status || '').toLowerCase()">{{ grant_application?.status }}</span></td></tr>
              <tr><th>Ceiling</th><td>\${{ (grant_application?.ceilingValue || 0).toLocaleString() }}</td></tr>
              <tr><th>Set-aside</th><td>{{ grant_application?.setAside }}</td></tr>
            </tbody>
          </table>
        </div>

        <div class="card">
          <h3>Amendments ({{ amendments.length }})</h3>
          <ul>
            <li *ngFor="let a of amendments">
              <strong>Amendment {{ a.number.toString().padStart(4, '0') }}</strong>
              <div style="font-size:0.8rem">{{ a.changeSummary }}</div>
              <small>Effective {{ a.effectiveAt | date:'mediumDate' }}</small>
            </li>
            <li *ngIf="amendments.length === 0"><em>No amendments.</em></li>
          </ul>
        </div>

        <div class="card">
          <h3>Public Q&amp;A</h3>
          <ul>
            <li *ngFor="let q of publicQna()" style="margin-bottom:0.75rem">
              <strong>Q:</strong> {{ q.question }}
              <div *ngIf="q.answer"><strong>A:</strong> {{ q.answer }}</div>
              <small style="color:var(--color-fg-muted)">Published {{ q.publishedAt | date:'mediumDate' }}</small>
            </li>
            <li *ngIf="publicQna().length === 0"><em>No published Q&amp;A yet.</em></li>
          </ul>
        </div>
      </div>
    </div>
  `,
})
export class OpportunityDetailComponent implements OnInit {
  id = '';
  grant_application: GrantApplication | null = null;
  amendments: Amendment[] = [];
  qna: Qna[] = [];

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.id = this.route.snapshot.params['id'];
    this.grant_application = FIXTURE_SOLICITATIONS.find((s) => s.id === this.id) ?? FIXTURE_SOLICITATIONS[0];
    this.amendments = FIXTURE_AMENDMENTS.filter((a) => a.grant_applicationId === this.id);
    this.qna = FIXTURE_QNA.filter((q) => q.grant_applicationId === this.id);
  }

  publicQna(): Qna[] {
    return this.qna.filter((q) => q.status === 'PUBLISHED');
  }

  sectionC(): string {
    return `C.1 SCOPE. ${this.grant_application?.description || ''}\n\nC.2 BACKGROUND. Karsun-aligned federal acquisition modernization scope.\n\nC.3 TASKS.\nTask 1: Service Operations\nTask 2: Continuous Monitoring\nTask 3: Incident Response`;
  }

  sectionL(): string {
    return 'L.5.2 Volume I — Technical (60 pages)\nL.5.3 Volume II — Past Performance\nL.5.4 Volume III — Price';
  }

  sectionM(): string {
    return 'M.3.1 Technical Approach (40%)\nM.3.2 Management Approach (25%)\nM.3.3 Past Performance (20%)\nM.3.4 Price (15%)';
  }
}
