import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { RoleService } from '../../services/role.service';
import { FIXTURE_EVALUATION, FIXTURE_PROPOSALS, FIXTURE_SCORES } from '../../services/mock-fixtures';
import { PeerReviewScore } from '../../models/peer-review';

/**
 * Reviewer Workspace (merit-review panel member view).
 *
 * Assigned applications only (criterion-by-criterion; narrative required).
 * Mirrors 2 CFR 200.205 merit-review discipline + Item 3 surface (reviewer
 * calling grant-application-service for application text is the canonical
 * circuit-breaker reproducer).
 */
@Component({
  selector: 'app-evaluator-workspace',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <div class="page-header">
      <div>
        <h2>Reviewer workspace</h2>
        <div class="subtitle">{{ role.current.displayName }} · Panel {{ peerReview.id }} · 2 CFR 200.205</div>
      </div>
      <a [routerLink]="['/peer-review', peerReview.id, 'consensus']"><button class="secondary">Consensus view →</button></a>
    </div>

    <div class="card">
      <h3>Merit-criteria scoring</h3>
      <p style="font-size:0.85rem;color:var(--color-fg-muted)">
        Score each application against each merit criterion. Narrative required
        for any rating other than Satisfactory.
      </p>
      <table>
        <thead>
          <tr>
            <th>Application</th>
            <th *ngFor="let c of peerReview.criteria">
              {{ c.name }}<br><small>{{ c.description }} · {{ c.weight }}%</small>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr *ngFor="let p of proposals">
            <td><strong>{{ p.vendorName }}</strong></td>
            <td *ngFor="let c of peerReview.criteria">
              <select [(ngModel)]="scoreFor(p.id, c.id).score">
                <option [ngValue]="9">Exceptional (9-10)</option>
                <option [ngValue]="7">Very Good (7-8)</option>
                <option [ngValue]="5">Satisfactory (5-6)</option>
                <option [ngValue]="3">Marginal (3-4)</option>
                <option [ngValue]="1">Unsatisfactory (1-2)</option>
              </select>
              <textarea rows="2" [(ngModel)]="scoreFor(p.id, c.id).narrative"
                        style="margin-top:0.25rem;font-size:0.8rem"
                        placeholder="Narrative…"></textarea>
            </td>
          </tr>
        </tbody>
      </table>
      <button style="margin-top:1rem">Submit scores</button>
    </div>
  `,
})
export class EvaluatorWorkspaceComponent {
  peerReview = FIXTURE_EVALUATION;
  proposals = FIXTURE_PROPOSALS;
  scoreCache: Record<string, PeerReviewScore> = {};

  constructor(public role: RoleService) {
    // Seed editable cache from fixture
    FIXTURE_SCORES.forEach((s) => {
      this.scoreCache[`${s.proposalId}:${s.meritCriterionId}`] = { ...s };
    });
  }

  scoreFor(proposalId: string, criterionId: string): PeerReviewScore {
    const key = `${proposalId}:${criterionId}`;
    if (!this.scoreCache[key]) {
      this.scoreCache[key] = {
        reviewerId: 'rv-current',
        reviewerName: this.role.current.displayName,
        proposalId,
        meritCriterionId: criterionId,
        score: 5,
        narrative: '',
        submittedAt: '',
      };
    }
    return this.scoreCache[key];
  }
}
