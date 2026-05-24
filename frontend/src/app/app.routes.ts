import { Routes } from '@angular/router';
import { GrantApplicationListComponent } from './components/grant-application-list/grant-application-list.component';
import { GrantApplicationCreateComponent } from './components/grant-application-create/grant-application-create.component';
import { PeerReviewPanelComponent } from './components/peer-review-panel/peer-review-panel.component';
import { OfficerDashboardComponent } from './components/officer-dashboard/officer-dashboard.component';
import { ReportsHubComponent } from './components/reports-hub/reports-hub.component';
import { GrantApplicationWizardComponent } from './components/grant-application-wizard/grant-application-wizard.component';
import { GrantApplicationEditorComponent } from './components/grant-application-editor/grant-application-editor.component';
import { AmendmentEditorComponent } from './components/amendment-editor/amendment-editor.component';
import { QnaTriageComponent } from './components/qna-triage/qna-triage.component';
import { ProposalIntakeComponent } from './components/proposal-intake/proposal-intake.component';
import { PublicOpportunitiesComponent } from './components/public-opportunities/public-opportunities.component';
import { OpportunityDetailComponent } from './components/opportunity-detail/opportunity-detail.component';
import { VendorDirectoryComponent } from './components/vendor-directory/vendor-directory.component';
import { VendorDetailComponent } from './components/vendor-detail/vendor-detail.component';
import { VendorPortalComponent } from './components/vendor-portal/vendor-portal.component';
import { EvaluatorWorkspaceComponent } from './components/evaluator-workspace/evaluator-workspace.component';
import { ConsensusSsddComponent } from './components/consensus-ssdd/consensus-ssdd.component';
import { AwardRecordComponent } from './components/award-record/award-record.component';
import { ContractAdminComponent } from './components/contract-admin/contract-admin.component';
import { CparReviewComponent } from './components/cpar-review/cpar-review.component';
import { AdminUsersComponent } from './components/admin-users/admin-users.component';
import { AdminConfigComponent } from './components/admin-config/admin-config.component';
import { AuditSearchComponent } from './components/audit-search/audit-search.component';
import { FindingsTrackerComponent } from './components/findings-tracker/findings-tracker.component';
import { roleGuard } from './services/role.guard';

export const routes: Routes = [
  { path: '', redirectTo: 'dashboard', pathMatch: 'full' },

  // — Officer landing + reports
  {
    path: 'dashboard',
    component: OfficerDashboardComponent,
    canMatch: [roleGuard('contracting_officer', 'contract_specialist', 'program_manager', 'ssa', 'sys_admin')],
  },
  {
    path: 'reports',
    component: ReportsHubComponent,
    canMatch: [roleGuard('contracting_officer', 'program_manager', 'ssa', 'sys_admin', 'oig_reviewer')],
  },
  // Drill-down report routes alias back to the hub (filter via query params in W5).
  { path: 'reports/pipeline', component: ReportsHubComponent },
  { path: 'reports/vendor-past-performance', component: ReportsHubComponent },
  { path: 'reports/contract-spend', component: ReportsHubComponent },

  // — GrantApplication lifecycle
  // NOTE: /grant_applications still routes to the LEGACY GrantApplicationListComponent
  // which hardcodes http://localhost:8081 (Item 8). PRESERVED as the W4 Tue
  // teaching artifact. New components route through environment.apiGatewayUrl.
  { path: 'grant-applications', component: GrantApplicationListComponent },
  {
    path: 'grant-applications/new',
    component: GrantApplicationWizardComponent,
    canMatch: [roleGuard('contracting_officer', 'contract_specialist')],
  },
  // Legacy single-page create form kept available under a sub-route so the
  // brownfield baseline is still demoable.
  { path: 'grant-applications/new-legacy', component: GrantApplicationCreateComponent },
  { path: 'grant-applications/:id/edit', component: GrantApplicationEditorComponent },
  {
    path: 'grant-applications/:id/amendments',
    component: AmendmentEditorComponent,
    canMatch: [roleGuard('contracting_officer', 'contract_specialist', 'program_manager')],
  },
  {
    path: 'grant-applications/:id/qa',
    component: QnaTriageComponent,
    canMatch: [roleGuard('contracting_officer', 'contract_specialist')],
  },
  {
    path: 'grant-applications/:id/proposals',
    component: ProposalIntakeComponent,
    canMatch: [roleGuard('contracting_officer', 'contract_specialist')],
  },

  // — Public-facing
  { path: 'public/opportunities', component: PublicOpportunitiesComponent },
  { path: 'public/opportunities/:id', component: OpportunityDetailComponent },

  // — Vendor management + portal
  {
    path: 'vendors',
    component: VendorDirectoryComponent,
    canMatch: [roleGuard('contracting_officer', 'contract_specialist', 'evaluator', 'program_manager', 'sys_admin')],
  },
  {
    path: 'vendors/:id',
    component: VendorDetailComponent,
    canMatch: [roleGuard('contracting_officer', 'contract_specialist', 'evaluator', 'program_manager', 'sys_admin')],
  },
  {
    path: 'vendor/proposals',
    component: VendorPortalComponent,
    canMatch: [roleGuard('vendor')],
  },

  // — PeerReview + source selection
  // Legacy peer-review-panel kept under a sub-route for instructor comparison.
  { path: 'peer-reviews', component: PeerReviewPanelComponent },
  {
    path: 'peer-review/workspace',
    component: EvaluatorWorkspaceComponent,
    canMatch: [roleGuard('evaluator', 'contracting_officer', 'sys_admin')],
  },
  {
    path: 'peer-review/:solId/consensus',
    component: ConsensusSsddComponent,
    canMatch: [roleGuard('ssa', 'contracting_officer', 'sys_admin')],
  },

  // — Post-award
  { path: 'awards/:id', component: AwardRecordComponent },
  {
    path: 'contracts/:id/admin',
    component: ContractAdminComponent,
    canMatch: [roleGuard('contracting_officer', 'program_manager', 'sys_admin', 'oig_reviewer')],
  },
  { path: 'contracts/:id/cpars', component: CparReviewComponent },

  // — Admin
  { path: 'admin/users', component: AdminUsersComponent, canMatch: [roleGuard('sys_admin')] },
  { path: 'admin/config', component: AdminConfigComponent, canMatch: [roleGuard('sys_admin')] },
  {
    path: 'admin/audit',
    component: AuditSearchComponent,
    canMatch: [roleGuard('sys_admin', 'oig_reviewer')],
  },
  {
    path: 'admin/findings',
    component: FindingsTrackerComponent,
    canMatch: [roleGuard('sys_admin', 'oig_reviewer')],
  },

  // — Catch-all → dashboard
  { path: '**', redirectTo: 'dashboard' },
];
