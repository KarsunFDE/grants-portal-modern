import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { GrantApplication } from '../../models/grant-application';
import { FIXTURE_SOLICITATIONS } from '../../services/mock-fixtures';

/**
 * Pre-submission editor for a draft grant application.
 *
 * Includes a side-panel Uniform-Guidance lookup (RAG over 2 CFR 200 / 45 CFR 75),
 * which is the W2 anchor surface (hybrid lexical + vector). The search input
 * here is the W2 Wed retrieval-boundary work surface — must filter by
 * agency_id (Item 10).
 */
@Component({
  selector: 'app-grant-application-editor',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>{{ grantApplication?.title || 'Draft grant application' }}</h2>
        <div class="subtitle">
          <span class="badge" [ngClass]="(grantApplication?.status || 'intake').toLowerCase()">{{ grantApplication?.status }}</span>
          · ALN {{ grantApplication?.assistanceListingNumber }} · {{ grantApplication?.fundingInstrument }}
        </div>
      </div>
      <div>
        <a [routerLink]="['/grant-applications', id, 'amendments']"><button class="secondary">NOFO amendments</button></a>
        <a [routerLink]="['/grant-applications', id, 'qa']"><button class="secondary">Applicant Q&amp;A</button></a>
        <a [routerLink]="['/grant-applications', id, 'proposals']"><button class="secondary">Applications</button></a>
      </div>
    </div>

    <div class="two-col">
      <div>
        <div class="card">
          <h3>Project Narrative</h3>
          <textarea rows="8" [(ngModel)]="sectionC"></textarea>
        </div>
        <div class="card">
          <h3>Budget Narrative</h3>
          <textarea rows="8" [(ngModel)]="sectionL"></textarea>
        </div>
        <div class="card">
          <h3>Merit-review criteria addressed</h3>
          <textarea rows="6" [(ngModel)]="sectionM"></textarea>
        </div>
      </div>

      <div>
        <div class="card">
          <h3>Uniform Guidance lookup (RAG)</h3>
          <p style="font-size:0.8rem;color:var(--color-fg-muted)">
            Hybrid lexical + Atlas Vector Search over 2 CFR 200 / 45 CFR 75.
            <em>Filtered by agency_id — Item 10 surface.</em>
          </p>
          <input [(ngModel)]="clauseQuery" (keyup.enter)="searchClauses()" placeholder="e.g., 200.430 allowable costs"/>
          <button (click)="searchClauses()" style="margin-top:0.5rem">Search</button>
          <ul *ngIf="clauseResults.length > 0">
            <li *ngFor="let c of clauseResults">
              <strong>{{ c.id }}</strong> — {{ c.title }}
              <button class="secondary" style="font-size:0.75rem;padding:0.1rem 0.35rem">Insert</button>
            </li>
          </ul>
        </div>

        <div class="card">
          <h3>State transition</h3>
          <select [(ngModel)]="targetState">
            <option value="INTAKE">INTAKE</option>
            <option value="SCREENING">SCREENING</option>
            <option value="PEER_REVIEW">PEER_REVIEW</option>
            <option value="AWARD_DECISION">AWARD_DECISION (Selecting Official)</option>
            <option value="WITHDRAWN">WITHDRAWN</option>
          </select>
          <button style="margin-top:0.5rem">Transition</button>
          <p style="font-size:0.75rem;color:var(--color-fg-muted);margin-top:0.5rem">
            ⚠ Transitions audit-logged (Item 2 race surface).
          </p>
        </div>
      </div>
    </div>
  `,
})
export class GrantApplicationEditorComponent implements OnInit {
  id = '';
  grantApplication: GrantApplication | null = null;
  sectionC = '';
  sectionL = '';
  sectionM = '';
  clauseQuery = '';
  clauseResults: { id: string; title: string }[] = [];
  targetState = 'SCREENING';

  constructor(private route: ActivatedRoute) {}

  ngOnInit(): void {
    this.id = this.route.snapshot.params['id'];
    this.grantApplication = FIXTURE_SOLICITATIONS.find((s) => s.id === this.id)
      ?? FIXTURE_SOLICITATIONS[0];
    this.sectionC = this.grantApplication.sections?.projectNarrative
      ?? `1. SIGNIFICANCE. ${this.grantApplication.description}`;
    this.sectionL = this.grantApplication.sections?.budgetNarrative
      ?? 'Personnel and fringe (Subpart E)…';
    this.sectionM = this.grantApplication.sections?.meritCriteria
      ?? 'Significance (40%)\nApproach (30%)\nFeasibility / Investigator (20%)\nBudget reasonableness (10%)';
  }

  searchClauses(): void {
    // Stub — in W2, hits POST /rag/clause-search over 2 CFR 200 / 45 CFR 75.
    const q = this.clauseQuery.toLowerCase();
    this.clauseResults = [
      { id: '2 CFR 200.204', title: 'Notices of funding opportunity' },
      { id: '2 CFR 200.205', title: 'Federal awarding agency review of merit of proposals' },
      { id: '2 CFR 200.430', title: 'Compensation — personal services (allowable costs)' },
    ].filter((c) => !q || c.id.toLowerCase().includes(q) || c.title.toLowerCase().includes(q));
  }
}
