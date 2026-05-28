import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { GrantApplicationService } from '../../services/grant-application.service';
import { GrantApplication, GrantApplicationCreate, GrantApplicationSections } from '../../models/grant-application';

/**
 * Multi-step Grant Application Wizard (SF-424 + 2 CFR 200 intake).
 *
 * Steps mirror the federal grants intake flow:
 * Step 1: Opportunity (NOFO #, Assistance Listing, awarding agency)
 * Step 2: Applicant (org, UEI, type, Principal Investigator)
 * Step 3: Project (title, narrative — AI-drafted via /draft-grant-application)
 * Step 4: Budget (federal request, cost-share match, period of performance)
 * Step 5: Review + submit for screening (INTAKE → SCREENING)
 *
 * Touches Item 4 (no Pydantic schema on AI output), Item 5 (legacy
 * LLMChain wired into the AI-orchestrator drafter), Item 9 (no
 * sanitization on description field).
 */
@Component({
  selector: 'app-grant-application-wizard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="page-header">
      <div>
        <h2>New grant application — intake wizard</h2>
        <div class="subtitle">SF-424 · 2 CFR 200 Uniform Guidance · AI-assisted</div>
      </div>
    </div>

    <div class="stepper">
      <span class="step" *ngFor="let s of steps; let i = index"
            [class.active]="i === step"
            [class.complete]="i < step">{{ i + 1 }}. {{ s }}</span>
    </div>

    <!-- Step 1: Opportunity -->
    <div class="card" *ngIf="step === 0">
      <h3>1. Funding opportunity</h3>
      <div class="two-col">
        <label><span class="label-text">Opportunity number (NOFO)</span>
          <input name="opportunityNumber" [(ngModel)]="model.opportunityNumber" placeholder="e.g., HHS-2026-ACF-OCS-EE-0123"/>
        </label>
        <label><span class="label-text">Assistance Listing (CFDA / ALN)</span>
          <input name="assistanceListingNumber" [(ngModel)]="model.assistanceListingNumber" placeholder="e.g., 93.243"/>
        </label>
        <label><span class="label-text">Awarding agency</span>
          <input name="awardingAgency" [(ngModel)]="model.awardingAgency" placeholder="e.g., HHS-NIH"/>
        </label>
        <label><span class="label-text">Funding instrument</span>
          <select name="fundingInstrument" [(ngModel)]="model.fundingInstrument">
            <option value="GRANT">Grant</option>
            <option value="COOPERATIVE_AGREEMENT">Cooperative Agreement</option>
          </select>
        </label>
      </div>
    </div>

    <!-- Step 2: Applicant -->
    <div class="card" *ngIf="step === 1">
      <h3>2. Applicant</h3>
      <div class="two-col">
        <label><span class="label-text">Applicant organization</span>
          <input name="applicantOrg" [(ngModel)]="model.applicantOrg" placeholder="e.g., State University of Example"/>
        </label>
        <label><span class="label-text">Unique Entity ID (SAM UEI)</span>
          <input name="applicantUei" [(ngModel)]="model.applicantUei" placeholder="12-char UEI"/>
        </label>
        <label><span class="label-text">Applicant type</span>
          <select name="applicantType" [(ngModel)]="model.applicantType">
            <option value="STATE">State government</option>
            <option value="COUNTY">County government</option>
            <option value="CITY">City / township government</option>
            <option value="NONPROFIT">Nonprofit (501(c)(3))</option>
            <option value="IHE">Institution of higher education</option>
            <option value="INDIVIDUAL">Individual</option>
            <option value="FOR_PROFIT">For-profit organization</option>
            <option value="OTHER">Other</option>
          </select>
        </label>
        <label><span class="label-text">Principal Investigator / Project Director</span>
          <input name="principalInvestigator" [(ngModel)]="model.principalInvestigator" placeholder="e.g., Dr. Jane Doe"/>
        </label>
      </div>
    </div>

    <!-- Step 3: Project -->
    <div class="card" *ngIf="step === 2">
      <h3>3. Project</h3>
      <label><span class="label-text">Project title</span>
        <input name="title" [(ngModel)]="model.title" placeholder="Descriptive title of the project (≤200 chars)"/>
      </label>
      <label><span class="label-text">Public project abstract</span>
        <textarea name="description" rows="3" [(ngModel)]="model.description"
                  placeholder="Public-facing project summary (rendered raw — see Debt Item 9)"></textarea>
      </label>
      <p style="font-size:0.85rem;color:var(--color-fg-muted)">
        Project narrative — AI-drafted via <code>POST /draft-grant-application</code> (ai-orchestrator).
        ⚠ Debt Item 4 (no Pydantic schema), Item 5 (legacy LLMChain.run wired here).
      </p>
      <button class="secondary" (click)="aiDraft('projectNarrative')">▦ AI-draft project narrative</button>
      <textarea name="projectNarrative" rows="10" [(ngModel)]="sections.projectNarrative"
                style="margin-top:0.5rem"></textarea>
    </div>

    <!-- Step 4: Budget -->
    <div class="card" *ngIf="step === 3">
      <h3>4. Budget &amp; period of performance</h3>
      <div class="two-col">
        <label><span class="label-text">Federal funds requested ($)</span>
          <input name="requestedAmountFederal" type="number" [(ngModel)]="model.requestedAmountFederal"/>
        </label>
        <label><span class="label-text">Cost-share / match ($)</span>
          <input name="costShareMatch" type="number" [(ngModel)]="model.costShareMatch"/>
        </label>
        <label><span class="label-text">Period of performance — start</span>
          <input name="periodOfPerformanceStart" type="date" [(ngModel)]="model.periodOfPerformanceStart"/>
        </label>
        <label><span class="label-text">Period of performance — end</span>
          <input name="periodOfPerformanceEnd" type="date" [(ngModel)]="model.periodOfPerformanceEnd"/>
        </label>
      </div>
      <p style="font-size:0.85rem;color:var(--color-fg-muted)">
        Budget narrative / justification (2 CFR 200 Subpart E allowable costs).
      </p>
      <textarea name="budgetNarrative" rows="6" [(ngModel)]="sections.budgetNarrative"
                placeholder="Personnel, fringe, travel, equipment, indirect (de minimis 10% or negotiated NICRA)…"></textarea>
    </div>

    <!-- Step 5: Review -->
    <div class="card" *ngIf="step === 4">
      <h3>5. Review &amp; submit for screening</h3>
      <p>Submitting transitions the application to <code>SCREENING</code>
         (eligibility &amp; completeness review per 2 CFR 200.205).</p>
      <table>
        <tbody>
          <tr><th>Project title</th><td>{{ model.title || '—' }}</td></tr>
          <tr><th>Opportunity / ALN</th><td>{{ model.opportunityNumber }} / {{ model.assistanceListingNumber }}</td></tr>
          <tr><th>Applicant / Type</th><td>{{ model.applicantOrg }} / {{ model.applicantType }}</td></tr>
          <tr><th>Principal Investigator</th><td>{{ model.principalInvestigator || '—' }}</td></tr>
          <tr><th>Funding instrument</th><td>{{ model.fundingInstrument }}</td></tr>
          <tr><th>Federal request / match</th><td>\${{ model.requestedAmountFederal?.toLocaleString() || '—' }} / \${{ model.costShareMatch?.toLocaleString() || '—' }}</td></tr>
          <tr><th>Project narrative length</th><td>{{ (sections.projectNarrative || '').length }} chars</td></tr>
          <tr><th>Budget narrative length</th><td>{{ (sections.budgetNarrative || '').length }} chars</td></tr>
        </tbody>
      </table>
    </div>

    <div style="margin-top:1rem;display:flex;gap:0.5rem;justify-content:space-between">
      <button class="secondary" (click)="back()" [disabled]="step === 0">← Back</button>
      <div>
        <button *ngIf="step < steps.length - 1" (click)="next()">Next →</button>
        <button *ngIf="step === steps.length - 1" (click)="submit()" [disabled]="submitting">
          {{ submitting ? 'Submitting…' : 'Submit for screening' }}
        </button>
      </div>
    </div>
    <div *ngIf="error" class="error-text">{{ error }}</div>
  `,
})
export class GrantApplicationWizardComponent {
  steps = ['Opportunity', 'Applicant', 'Project', 'Budget', 'Review'];
  step = 0;
  submitting = false;
  error: string | null = null;

  model: GrantApplicationCreate = {
    agencyId: 'HHS-NIH',
    title: '',
    description: '',
    status: 'INTAKE',
    opportunityNumber: '',
    assistanceListingNumber: '',
    awardingAgency: 'HHS-NIH',
    applicantOrg: '',
    applicantUei: '',
    applicantType: 'NONPROFIT',
    principalInvestigator: '',
    fundingInstrument: 'GRANT',
    requestedAmountFederal: undefined,
    costShareMatch: undefined,
  };

  sections: GrantApplicationSections = {};

  constructor(private svc: GrantApplicationService, private router: Router) {}

  back(): void {
    if (this.step > 0) this.step--;
  }

  next(): void {
    if (this.step < this.steps.length - 1) this.step++;
  }

  aiDraft(section: 'projectNarrative'): void {
    // Stubbed — in W2 this hits POST /draft-grant-application through the
    // gateway. For instructor demo, populate plausible placeholder text.
    this.sections.projectNarrative =
      `1. SIGNIFICANCE. This project addresses a documented need served by ` +
      `${this.model.awardingAgency || 'the awarding agency'} under Assistance Listing ` +
      `${this.model.assistanceListingNumber || '[ALN]'}. ` +
      `${this.model.description || '[project abstract not yet entered]'}\n\n` +
      `2. APPROACH. ${this.model.applicantOrg || 'The applicant organization'} will ` +
      `execute the following objectives over the period of performance:\n` +
      `Objective 1: Program design and stakeholder engagement\n` +
      `Objective 2: Service delivery and capacity building\n` +
      `Objective 3: Performance measurement and reporting (2 CFR 200.301)\n\n` +
      `3. FEASIBILITY. The Principal Investigator, ${this.model.principalInvestigator || '[PI]'}, ` +
      `brings relevant experience; the budget and timeline are realistic for the proposed scope.\n\n` +
      `[AI-DRAFTED placeholder — to be reviewed by the Program Officer / PI before submission. Item 4 / Item 5 surface.]`;
  }

  submit(): void {
    this.submitting = true;
    this.error = null;
    const payload: GrantApplicationCreate = {
      ...this.model,
      status: 'SCREENING',
      sections: this.sections,
    };
    this.svc.create(payload).subscribe({
      next: (s: GrantApplication) => {
        this.submitting = false;
        this.router.navigate(['/grant-applications', s.id || 'app-new', 'edit']);
      },
      error: (err) => {
        // Brownfield reality: create may fail; for instructor demo, still
        // route to the editor as if it succeeded.
        this.submitting = false;
        this.router.navigate(['/grant-applications']);
      },
    });
  }
}
