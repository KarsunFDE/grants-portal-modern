import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { GrantApplicationService } from '../../services/grant-application.service';
import { GrantApplicationCreate } from '../../models/grant-application';

/**
 * New grant-application form (quick intake — the full SF-424 flow is the wizard).
 *
 * ⚠ DELIBERATE — Item 8 reinforcement / Item 9 reinforcement:
 *   - The `description` textarea has NO maxlength, NO required validator,
 *     NO HTML-strip on submit. Pairs with backend Item 9 (raw HTML accepted).
 *   - `title` field has no `required` or `minlength` — empty title submits.
 *   - `agencyId` is a free-text input; should be a dropdown of the user's
 *     authorized agencies.
 */
@Component({
  selector: 'app-grant-application-create',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <h2>New grant application</h2>
    <form (ngSubmit)="onSubmit()" #form="ngForm">
      <p>
        <label>Project title<br>
          <input name="title" [(ngModel)]="model.title"/>
        </label>
      </p>
      <p>
        <label>Opportunity number (NOFO)<br>
          <input name="opportunityNumber" [(ngModel)]="model.opportunityNumber"/>
        </label>
      </p>
      <p>
        <label>Applicant organization<br>
          <input name="applicantOrg" [(ngModel)]="model.applicantOrg"/>
        </label>
      </p>
      <p>
        <label>Awarding agency<br>
          <input name="agencyId" [(ngModel)]="model.agencyId"/>
        </label>
      </p>
      <p>
        <label>Project abstract<br>
          <textarea name="description" [(ngModel)]="model.description" rows="6"></textarea>
        </label>
      </p>
      <p>
        <button type="submit" [disabled]="submitting">
          {{ submitting ? 'Creating…' : 'Create' }}
        </button>
      </p>
      <p *ngIf="error" style="color: crimson">{{ error }}</p>
    </form>
  `,
})
export class GrantApplicationCreateComponent {
  model: GrantApplicationCreate = {
    agencyId: '',
    title: '',
    description: '',
    status: 'INTAKE',
    opportunityNumber: '',
    applicantOrg: '',
  };
  submitting = false;
  error: string | null = null;

  constructor(
    private svc: GrantApplicationService,
    private router: Router,
  ) {}

  onSubmit(): void {
    this.submitting = true;
    this.error = null;
    this.svc.create(this.model).subscribe({
      next: () => {
        this.submitting = false;
        this.router.navigate(['/grant-applications']);
      },
      error: (err) => {
        this.error = `Create failed: ${err.message ?? err}`;
        this.submitting = false;
      },
    });
  }
}
