import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { GrantApplication } from '../../models/grant-application';
import { RoleService } from '../../services/role.service';
import { FIXTURE_SOLICITATIONS } from '../../services/mock-fixtures';

const ORCH_URL = 'http://localhost:8000';

interface GateBtn { value: string; label: string; primary?: boolean; danger?: boolean; }

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
        <button class="secondary" [routerLink]="['/grant-applications', id, 'amendments']">NOFO amendments</button>
        <button class="secondary" [routerLink]="['/grant-applications', id, 'qa']">Applicant Q&amp;A</button>
        <button class="secondary" [routerLink]="['/grant-applications', id, 'proposals']">Applications</button>
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
          <button (click)="searchClauses()" style="margin-top:0.5rem" [disabled]="clauseSearchLoading">
            {{ clauseSearchLoading ? 'Searching…' : 'Search' }}
          </button>
          <ul *ngIf="clauseResults.length > 0">
            <li *ngFor="let c of clauseResults">
              <strong>{{ c.id }}</strong> — {{ c.title }}
            </li>
          </ul>
        </div>

        <!-- HITL Workflow Panel -->
        <div class="card">
          <h3>AI Workflow <span style="font-size:0.75rem;font-weight:normal;color:var(--color-fg-muted)">(HITL · LangGraph)</span></h3>

          <!-- Not started -->
          <ng-container *ngIf="!workflowRunId">
            <p style="font-size:0.85rem;color:var(--color-fg-muted)">
              4-gate screening: eligibility → COI → factor suggest → award decision.
            </p>
            <button (click)="startWorkflow()" [disabled]="workflowLoading">
              {{ workflowLoading ? 'Starting…' : '▶ Start AI Review' }}
            </button>
            <div *ngIf="workflowError" style="color:crimson;font-size:0.85rem;margin-top:0.5rem">{{ workflowError }}</div>
          </ng-container>

          <!-- Active workflow -->
          <ng-container *ngIf="workflowRunId">
            <div style="font-size:0.75rem;color:var(--color-fg-muted);margin-bottom:0.75rem">
              Run <code>{{ workflowRunId | slice:0:8 }}…</code>
              · Stage: <strong>{{ currentStage || '—' }}</strong>
            </div>

            <!-- PAUSED_AT_GATE -->
            <ng-container *ngIf="workflowStatus === 'PAUSED_AT_GATE'">
              <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.75rem">
                <span class="badge screening">⏸ {{ activeGateId }}</span>
                <span style="font-size:0.8rem">Awaiting human decision</span>
              </div>

              <div *ngIf="pendingInterrupt" style="font-size:0.82rem;background:var(--color-bg-subtle,#f6f8fa);padding:0.6rem;border-radius:4px;margin-bottom:0.75rem">
                <div *ngIf="pendingInterrupt.grounding_status">
                  Grounding: <strong [style.color]="groundingColor(pendingInterrupt.grounding_status)">{{ pendingInterrupt.grounding_status }}</strong>
                  <span *ngIf="pendingInterrupt.confidence_score != null"> · Confidence: {{ (pendingInterrupt.confidence_score * 100).toFixed(0) }}%</span>
                </div>
                <div *ngIf="pendingInterrupt.human_review_reasons?.length" style="margin-top:0.25rem">
                  Flags: <strong style="color:#c1232b">{{ pendingInterrupt.human_review_reasons.join(', ') }}</strong>
                </div>
                <div *ngIf="pendingInterrupt.coi_detected != null" style="margin-top:0.25rem">
                  COI detected: <strong>{{ pendingInterrupt.coi_detected ? '⚠ YES' : 'None' }}</strong>
                </div>
                <div *ngIf="pendingInterrupt.reviewer_candidates?.length" style="margin-top:0.25rem">
                  Reviewers: {{ pendingInterrupt.reviewer_candidates.length }} candidates
                  (top: {{ pendingInterrupt.reviewer_candidates[0]?.name }})
                </div>
                <div *ngIf="pendingInterrupt.retrieved_sources?.length" style="margin-top:0.25rem;font-size:0.75rem;color:var(--color-fg-muted)">
                  Sources: {{ pendingInterrupt.retrieved_sources.join(' · ') }}
                </div>
              </div>

              <textarea [(ngModel)]="rationale" rows="2"
                        placeholder="Rationale (required)"
                        style="margin-bottom:0.5rem"></textarea>

              <div style="display:flex;gap:0.4rem;flex-wrap:wrap;margin-bottom:0.5rem">
                <button *ngFor="let d of gateDecisions()"
                        (click)="resumeWorkflow(d.value)"
                        [disabled]="workflowLoading || !rationale.trim()"
                        [class.secondary]="!d.primary"
                        [style.background]="d.danger ? '#c1232b' : null"
                        [style.color]="d.danger ? '#fff' : null"
                        [style.borderColor]="d.danger ? '#c1232b' : null">
                  {{ workflowLoading ? '…' : d.label }}
                </button>
              </div>

              <label *ngIf="pendingInterrupt?.blocked" style="font-size:0.75rem;display:flex;align-items:center;gap:0.35rem;cursor:pointer">
                <input type="checkbox" [(ngModel)]="overrideFlag">
                Override grounding block (supervisor)
              </label>

              <div *ngIf="workflowError" style="color:crimson;font-size:0.85rem;margin-top:0.5rem">{{ workflowError }}</div>
            </ng-container>

            <!-- COMPLETED -->
            <ng-container *ngIf="workflowStatus === 'COMPLETED'">
              <div style="display:flex;align-items:center;gap:0.5rem">
                <span class="badge" style="background:#1a7f37;color:#fff">✓ AWARDED</span>
                <span style="font-size:0.85rem">Workflow complete — POST_AWARD</span>
              </div>
              <button class="secondary" style="margin-top:0.75rem" (click)="resetWorkflow()">Start new run</button>
            </ng-container>

            <!-- DENIED -->
            <ng-container *ngIf="workflowStatus === 'DENIED'">
              <div style="display:flex;align-items:center;gap:0.5rem">
                <span class="badge" style="background:#c1232b;color:#fff">✗ DENIED</span>
                <span style="font-size:0.85rem">{{ workflowMessage || 'Application denied' }}</span>
              </div>
              <button class="secondary" style="margin-top:0.75rem" (click)="resetWorkflow()">Start new run</button>
            </ng-container>

            <!-- ERROR -->
            <div *ngIf="workflowStatus === 'ERROR'" style="color:crimson;font-size:0.85rem">
              Workflow error. <button class="secondary" (click)="resetWorkflow()">Reset</button>
            </div>
          </ng-container>
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

  // Workflow state
  workflowRunId = '';
  workflowStatus = '';
  currentStage = '';
  activeGateId = '';
  pendingInterrupt: any = null;
  workflowLoading = false;
  workflowError = '';
  workflowMessage = '';
  rationale = '';
  overrideFlag = false;

  constructor(
    private route: ActivatedRoute,
    private http: HttpClient,
    public role: RoleService,
  ) {}

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

  clauseSearchLoading = false;

  searchClauses(): void {
    if (!this.clauseQuery.trim()) return;
    this.clauseSearchLoading = true;
    this.clauseResults = [];
    this.http.post<any>(`${ORCH_URL}/rag/clause-search`, {
      query: this.clauseQuery,
      tenant_id: 'demo',
      top_k: 5,
    }).subscribe({
      next: (r) => {
        this.clauseResults = (r.hits || []).map((h: any) => ({ id: h.clause_id, title: h.title }));
        this.clauseSearchLoading = false;
      },
      error: () => { this.clauseSearchLoading = false; },
    });
  }

  gateDecisions(): GateBtn[] {
    switch (this.activeGateId) {
      case 'GATE_1': return [
        { value: 'APPROVE', label: '✓ Approve', primary: true },
        { value: 'RETURN_FOR_FIXES', label: '↩ Return for Fixes' },
        { value: 'REJECT', label: '✗ Reject', danger: true },
      ];
      case 'GATE_2': return [
        { value: 'RESOLVE_AND_CONTINUE', label: '✓ Resolve & Continue', primary: true },
        { value: 'REMOVE_REVIEWER', label: 'Remove Reviewer' },
        { value: 'OVERRIDE', label: 'Override' },
      ];
      case 'GATE_3': return [
        { value: 'ACCEPT', label: '✓ Accept Factors', primary: true },
        { value: 'EDIT', label: '✎ Edit' },
        { value: 'REJECT', label: '✗ Reject', danger: true },
      ];
      case 'GATE_4': return [
        { value: 'AWARD', label: '★ Award Grant', primary: true },
        { value: 'RETURN_TO_REVIEW', label: '↩ Return to Review' },
        { value: 'DO_NOT_AWARD', label: '✗ Do Not Award', danger: true },
      ];
      default: return [];
    }
  }

  private actorRole(): string {
    if (this.activeGateId === 'GATE_2') return 'REVIEW_LEAD';
    if (this.activeGateId === 'GATE_3') return 'HUMAN_REVIEWER';
    return 'GRANTS_OFFICER';
  }

  groundingColor(status: string): string {
    if (status === 'GROUNDED') return '#1a7f37';
    if (status === 'LOW_CONFIDENCE') return '#b08800';
    return '#c1232b';
  }

  startWorkflow(): void {
    this.workflowLoading = true;
    this.workflowError = '';
    const app = this.grantApplication;
    this.http.post<any>(`${ORCH_URL}/workflow/start`, {
      tenant_id: 'demo',
      grant_application_id: this.id,
      applicant_type: app?.applicantType ?? 'NONPROFIT',
      applicant_uei: app?.applicantUei ?? '',
      applicant_org: app?.applicantOrg ?? '',
      assistance_listing_number: app?.assistanceListingNumber ?? '',
      requested_amount_federal: app?.requestedAmountFederal ?? 0,
    }).subscribe({
      next: (r) => this.applyResponse(r),
      error: (e) => {
        this.workflowLoading = false;
        this.workflowError = `Start failed: ${e.message ?? e.status ?? 'unknown error'}`;
      },
    });
  }

  resumeWorkflow(decision: string): void {
    if (!this.rationale.trim()) {
      this.workflowError = 'Rationale required before deciding.';
      return;
    }
    this.workflowLoading = true;
    this.workflowError = '';
    this.http.post<any>(
      `${ORCH_URL}/workflow/resume`,
      {
        workflow_run_id: this.workflowRunId,
        gate_decision: decision,
        actor_id: `${this.role.currentRole}-demo`,
        actor_role: this.actorRole(),
        rationale: this.rationale,
        override_flag: this.overrideFlag,
      },
      { headers: new HttpHeaders({ 'X-Tenant-Id': 'demo' }) },
    ).subscribe({
      next: (r) => {
        this.rationale = '';
        this.overrideFlag = false;
        this.applyResponse(r);
      },
      error: (e) => {
        this.workflowLoading = false;
        this.workflowError = `Resume failed: ${e.message ?? e.status ?? 'unknown error'}`;
      },
    });
  }

  resetWorkflow(): void {
    this.workflowRunId = '';
    this.workflowStatus = '';
    this.currentStage = '';
    this.activeGateId = '';
    this.pendingInterrupt = null;
    this.workflowError = '';
    this.workflowMessage = '';
    this.rationale = '';
    this.overrideFlag = false;
  }

  private applyResponse(r: any): void {
    this.workflowLoading = false;
    this.workflowRunId = r.workflow_run_id ?? this.workflowRunId;
    this.workflowStatus = r.status ?? '';
    this.currentStage = r.current_stage ?? '';
    this.activeGateId = r.active_gate_id ?? '';
    this.pendingInterrupt = r.pending_interrupt ?? null;
    this.workflowMessage = r.message ?? '';
  }
}
