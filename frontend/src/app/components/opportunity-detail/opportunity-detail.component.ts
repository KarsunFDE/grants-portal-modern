import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { GrantApplication } from '../../models/grant-application';
import { Amendment } from '../../models/amendment';
import { Qna } from '../../models/qna';
import { FIXTURE_SOLICITATIONS, FIXTURE_AMENDMENTS, FIXTURE_QNA } from '../../services/mock-fixtures';

/**
 * Public-facing funding-opportunity (NOFO) detail.
 *
 * Renders project narrative, budget narrative, merit criteria, amendments
 * timeline, public Q&A history. The description renders raw (Item 9) — a
 * teaching surface for W4 Wed AI Security (prompt-injection-via-stored-content).
 */
@Component({
  selector: 'app-opportunity-detail',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>{{ grantApplication?.title }}</h2>
        <div class="subtitle">
          {{ grantApplication?.opportunityNumber }} · {{ grantApplication?.awardingAgency || grantApplication?.agencyId }} · ALN {{ grantApplication?.assistanceListingNumber }}
        </div>
      </div>
      <a routerLink="/public/opportunities"><button class="secondary">← All opportunities</button></a>
    </div>

    <div class="two-col">
      <div>
        <div class="card">
          <h3>Project abstract</h3>
          <!-- ⚠ Item 9: description rendered raw via innerHTML in the production
               version. Here we use text interpolation but the backend stores
               raw HTML; cohort discovers the W4 surface in the network tab. -->
          <p>{{ grantApplication?.description }}</p>
        </div>

        <div class="card">
          <h3>Project Narrative</h3>
          <pre style="white-space:pre-wrap;font-family:inherit">{{ sectionC() }}</pre>
        </div>

        <div class="card">
          <h3>Budget Narrative</h3>
          <pre style="white-space:pre-wrap;font-family:inherit">{{ sectionL() }}</pre>
        </div>

        <div class="card">
          <h3>Merit-review criteria</h3>
          <pre style="white-space:pre-wrap;font-family:inherit">{{ sectionM() }}</pre>
        </div>
      </div>

      <div>
        <div class="card">
          <h3>Key dates &amp; funding</h3>
          <table>
            <tbody>
              <tr><th>Posted</th><td>{{ grantApplication?.createdAt | date:'mediumDate' }}</td></tr>
              <tr><th>Period of performance</th><td>{{ grantApplication?.periodOfPerformanceEnd ? (grantApplication?.periodOfPerformanceEnd | date:'mediumDate') : '—' }}</td></tr>
              <tr><th>Status</th><td><span class="badge" [ngClass]="(grantApplication?.status || '').toLowerCase()">{{ grantApplication?.status }}</span></td></tr>
              <tr><th>Federal request</th><td>\${{ (grantApplication?.requestedAmountFederal || 0).toLocaleString() }}</td></tr>
              <tr><th>Funding instrument</th><td>{{ grantApplication?.fundingInstrument }}</td></tr>
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
  grantApplication: GrantApplication | null = null;
  amendments: Amendment[] = [];
  qna: Qna[] = [];

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.id = this.route.snapshot.params['id'];
    this.grantApplication = FIXTURE_SOLICITATIONS.find((s) => s.id === this.id) ?? FIXTURE_SOLICITATIONS[0];
    this.amendments = FIXTURE_AMENDMENTS.filter((a) => a.grantApplicationId === this.id);
    this.qna = FIXTURE_QNA.filter((q) => q.grantApplicationId === this.id);
  }

  publicQna(): Qna[] {
    return this.qna.filter((q) => q.status === 'PUBLISHED');
  }

  sectionC(): string {
    return this.grantApplication?.sections?.projectNarrative
      ?? `1. SIGNIFICANCE. ${this.grantApplication?.description || ''}\n\n2. APPROACH. Program design, service delivery, and capacity building over the period of performance.\n\n3. FEASIBILITY. Investigator experience and realistic timeline.`;
  }

  sectionL(): string {
    return this.grantApplication?.sections?.budgetNarrative
      ?? 'Personnel and fringe (2 CFR 200 Subpart E)\nTravel and equipment\nIndirect costs (de minimis 10% or negotiated NICRA)';
  }

  sectionM(): string {
    return this.grantApplication?.sections?.meritCriteria
      ?? 'Significance (40%)\nApproach (30%)\nFeasibility / Investigator (20%)\nBudget reasonableness (10%)';
  }
}
