import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { RoleService } from '../../services/role.service';
import { FIXTURE_EVALUATION, FIXTURE_PROPOSALS, FIXTURE_SCORES } from '../../services/mock-fixtures';
import { MeritCriterion } from '../../models/peer-review';

/**
 * Merit-review consensus + funding-recommendation draft (2 CFR 200.205).
 *
 * SSA-only gate stands in for the Selecting Official who approves the panel's
 * funding recommendation; this authority cannot be delegated. This is the
 * W3 LangGraph HITL #5 deep-dive surface — interrupt-before-node at
 * "consensus complete" and "award decision ready".
 */
@Component({
  selector: 'app-consensus-ssdd',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Merit review — consensus &amp; funding recommendation</h2>
        <div class="subtitle">2 CFR 200.205 · Selecting Official authority non-delegable</div>
      </div>
      <a routerLink="/peer-review/workspace"><button class="secondary">← Reviewer workspace</button></a>
    </div>

    <div class="hitl-banner">
      <strong>HITL gate (W3 #5 — LangGraph deep-dive):</strong>
      AI drafts the funding-recommendation narrative; the Selecting Official must review &amp; approve.
      LangGraph interrupt-before-node fires at "award decision ready".
    </div>

    <div class="card">
      <h3>Consensus score matrix</h3>
      <table>
        <thead>
          <tr>
            <th>Application</th>
            <th *ngFor="let c of peerReview.criteria">{{ c.name }} <small>({{ c.weight }}%)</small></th>
            <th>Weighted total</th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let p of proposals">
            <td><strong>{{ p.vendorName }}</strong></td>
            <td *ngFor="let c of peerReview.criteria">{{ avgScore(p.id, c.id) | number:'1.0-1' }}</td>
            <td><strong>{{ weighted(p.id) | number:'1.0-2' }}</strong></td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="card">
      <h3>Funding recommendation draft (AI-assisted)</h3>
      <button class="secondary" (click)="aiDraft()">▦ AI-draft recommendation narrative</button>
      <textarea rows="10" [(ngModel)]="ssddNarrative" style="margin-top:0.5rem"></textarea>
      <div style="margin-top:0.75rem;display:flex;gap:0.5rem;align-items:center">
        <button [disabled]="role.currentRole !== 'ssa'" (click)="sign()">
          ✓ Approve &amp; record award decision
        </button>
        <small *ngIf="role.currentRole !== 'ssa'" style="color:var(--color-fg-muted)">
          Only the Selecting Official can approve.
        </small>
      </div>
      <div *ngIf="signed" class="card" style="background:var(--color-bg);margin-top:1rem">
        <strong>✓ Award decision recorded:</strong> {{ winningName() }} —
        <a routerLink="/awards/aw-2026-001">aw-2026-001</a>
      </div>
    </div>
  `,
})
export class ConsensusSsddComponent {
  peerReview = FIXTURE_EVALUATION;
  proposals = FIXTURE_PROPOSALS;
  ssddNarrative = '';
  signed = false;

  constructor(public role: RoleService, route: ActivatedRoute) {
    // Route param `solId` reserved for multi-peerReview routing.
  }

  avgScore(proposalId: string, criterionId: string): number {
    const matches = FIXTURE_SCORES.filter((s) => s.proposalId === proposalId && s.meritCriterionId === criterionId);
    if (!matches.length) return 5;
    return matches.reduce((sum, s) => sum + s.score, 0) / matches.length;
  }

  weighted(proposalId: string): number {
    return this.peerReview.criteria.reduce(
      (sum: number, c: MeritCriterion) => sum + this.avgScore(proposalId, c.id) * (c.weight / 100),
      0,
    );
  }

  aiDraft(): void {
    const best = this.proposals
      .map((p) => ({ id: p.id, name: p.vendorName, score: this.weighted(p.id) }))
      .sort((a, b) => b.score - a.score)[0];
    this.ssddNarrative =
      `Funding Recommendation Memo\n\n` +
      `Pursuant to 2 CFR 200.205, the merit-review panel recommends that ` +
      `${best.name} be selected for funding under the published merit criteria. ` +
      `The weighted consensus score of ${best.score.toFixed(2)} reflects the panel's ` +
      `assessment of significance, approach, and feasibility across the application.\n\n` +
      `[AI-DRAFTED — the Selecting Official must review for factual accuracy. Item 4 (no Pydantic schema), Item 5 (legacy LLMChain).]`;
  }

  sign(): void {
    if (this.role.currentRole !== 'ssa') return;
    this.signed = true;
  }

  winningName(): string {
    const best = this.proposals
      .map((p) => ({ id: p.id, name: p.vendorName, score: this.weighted(p.id) }))
      .sort((a, b) => b.score - a.score)[0];
    return best?.name ?? '—';
  }
}
