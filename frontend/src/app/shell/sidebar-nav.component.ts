import { Component, OnDestroy, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { Subscription } from 'rxjs';
import { RoleService } from '../services/role.service';
import { Role, RoleProfile } from '../models/roles';

interface NavLink {
  label: string;
  route: string;
  roles: Role[];           // empty = visible to all authenticated
}
interface NavGroup {
  title: string;
  links: NavLink[];
}

const ALL_AUTHENTICATED: Role[] = [
  'contracting_officer', 'contract_specialist', 'program_manager',
  'ssa', 'evaluator', 'vendor', 'oig_reviewer', 'sys_admin',
];

// Grants-management IA (SF-424 intake → 2 CFR 200 merit review → award → post-award
// reporting). Roles are unchanged from the inherited acquisition `Role` enum — the
// personas in roles.ts are relabeled to grants equivalents (GMO↔contracting_officer,
// Program Officer↔program_manager, Peer Reviewer↔evaluator, Grantee/PI↔vendor) so
// route guards and the role enum stay stable. Inherited acquisition-only surfaces
// (Vendor Directory, Contract Admin, CPAR) have no grants equivalent yet, so they are
// grouped under "Legacy (pre-grants)" rather than deleted — the pair prunes/repurposes
// them in W4–W5 (mirrors the contract-payment-flow sibling's inherited-surface handling).
const NAV: NavGroup[] = [
  {
    title: 'Workspace',
    links: [
      { label: 'Program Officer Dashboard', route: '/dashboard', roles: ['contracting_officer', 'contract_specialist', 'program_manager', 'ssa'] },
      { label: 'Peer Reviewer Workspace', route: '/peer-review/workspace', roles: ['evaluator', 'contracting_officer'] },
      { label: 'Grantee Portal', route: '/vendor/proposals', roles: ['vendor'] },
    ],
  },
  {
    title: 'Grant Applications',
    links: [
      { label: 'Applications Index', route: '/grant-applications', roles: ['contracting_officer', 'contract_specialist', 'program_manager'] },
      { label: 'New Application', route: '/grant-applications/new', roles: ['contracting_officer', 'contract_specialist'] },
      { label: 'Funding Opportunity Search', route: '/public/opportunities', roles: [] },
    ],
  },
  {
    title: 'Merit Review',
    links: [
      { label: 'Merit Review Panel', route: '/peer-review/eval-0142/consensus', roles: ['ssa', 'contracting_officer'] },
    ],
  },
  {
    title: 'Awards',
    links: [
      { label: 'Award Decision', route: '/awards/aw-2026-001', roles: ['contracting_officer', 'program_manager', 'vendor'] },
      { label: 'Post-Award Reporting', route: '/contracts/ctr-0001/admin', roles: ['contracting_officer', 'program_manager'] },
    ],
  },
  {
    title: 'Reports',
    links: [
      { label: 'All Reports', route: '/reports', roles: ['contracting_officer', 'program_manager', 'ssa', 'sys_admin', 'oig_reviewer'] },
    ],
  },
  {
    title: 'Admin',
    links: [
      { label: 'User & Role Admin', route: '/admin/users', roles: ['sys_admin'] },
      { label: 'System Config', route: '/admin/config', roles: ['sys_admin'] },
      { label: 'Audit Log Search', route: '/admin/audit', roles: ['sys_admin', 'oig_reviewer'] },
      { label: 'OIG Findings Tracker', route: '/admin/findings', roles: ['sys_admin', 'oig_reviewer'] },
    ],
  },
  {
    // Inherited acquisition surfaces with no grants equivalent yet. Routes/components
    // are preserved; the pair prunes or repurposes these in W4–W5 modernization.
    title: 'Legacy (pre-grants)',
    links: [
      { label: 'Vendor Directory', route: '/vendors', roles: ['contracting_officer', 'contract_specialist', 'evaluator', 'program_manager'] },
      { label: 'Contract Admin', route: '/contracts/ctr-0001/admin', roles: ['contracting_officer', 'program_manager'] },
      { label: 'CPAR Reviews', route: '/contracts/ctr-0001/cpars', roles: ['contracting_officer', 'program_manager', 'vendor'] },
    ],
  },
];

@Component({
  selector: 'app-sidebar-nav',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive],
  template: `
    <nav class="sidebar">
      <ng-container *ngFor="let group of visibleGroups; trackBy: trackGroup">
        <div class="sidebar-section-title">{{ group.title }}</div>
        <a *ngFor="let link of group.links; trackBy: trackLink"
           [routerLink]="link.route"
           routerLinkActive="active">{{ link.label }}</a>
      </ng-container>
    </nav>
  `,
})
export class SidebarNavComponent implements OnInit, OnDestroy {
  visibleGroups: NavGroup[] = [];
  private sub?: Subscription;

  constructor(public role: RoleService) {}

  ngOnInit(): void {
    this.recompute(this.role.currentRole);
    this.sub = this.role.profile$.subscribe((p) => this.recompute(p.role));
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  trackGroup = (_: number, g: NavGroup) => g.title;
  trackLink = (_: number, l: NavLink) => l.route;

  private recompute(current: Role): void {
    this.visibleGroups = NAV
      .map((g) => ({
        ...g,
        links: g.links.filter((l) =>
          l.roles.length === 0 || l.roles.includes(current) || current === 'sys_admin',
        ),
      }))
      .filter((g) => g.links.length > 0);
  }
}
