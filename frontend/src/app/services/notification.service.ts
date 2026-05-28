import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { Notification } from '../models/notification';

/**
 * In-app notification bus (bell icon + drawer).
 *
 * Per feature-inventory-target.md notification table. Item 6
 * (correlation-ID mismatch) is reinforced by the fact that this
 * client-side mock generates its own UUID independent of the
 * triggering service-side correlation ID.
 */
@Injectable({ providedIn: 'root' })
export class NotificationService {
  private readonly subject = new BehaviorSubject<Notification[]>(this.seed());
  readonly items$: Observable<Notification[]> = this.subject.asObservable();

  markRead(id: string): void {
    this.subject.next(
      this.subject.value.map((n) =>
        n.id === id ? { ...n, readAt: new Date().toISOString() } : n,
      ),
    );
  }

  markAllRead(): void {
    const ts = new Date().toISOString();
    this.subject.next(
      this.subject.value.map((n) => ({ ...n, readAt: n.readAt ?? ts })),
    );
  }

  unreadCount(): number {
    return this.subject.value.filter((n) => !n.readAt).length;
  }

  private seed(): Notification[] {
    return [
      {
        id: 'n-1001',
        kind: 'NOFO_PUBLISHED',
        title: 'NOFO published — HHS-2026-ACF-0142 (Rural Health Capacity)',
        body: 'Program Officer Shah posted the funding opportunity. Application window closes 2026-07-15 (2 CFR 200.204).',
        recipientRole: 'program_manager',
        link: '/public/opportunities/op-0142',
        createdAt: new Date(Date.now() - 1000 * 60 * 12).toISOString(),
        readAt: null,
      },
      {
        id: 'n-1002',
        kind: 'APPLICATION_RECEIVED',
        title: 'Grant application received — Appalachian Regional Health Coalition',
        body: 'SF-424 submitted under HHS-2026-ACF-0142 (applicant UEI AB1CDE2FGHI3). Eligibility check pending.',
        recipientRole: 'program_manager',
        link: '/grant-applications/app-0203',
        createdAt: new Date(Date.now() - 1000 * 60 * 60 * 2).toISOString(),
        readAt: null,
      },
      {
        id: 'n-1003',
        kind: 'MERIT_REVIEW_DUE',
        title: 'Merit review scoring due in 5 days',
        body: 'PeerReview panel for HHS-2026-ACF-0142 — 3 of 6 merit criteria scored (2 CFR 200.205). COI attestation on file.',
        recipientRole: 'evaluator',
        link: '/peer-review/workspace',
        createdAt: new Date(Date.now() - 1000 * 60 * 60 * 8).toISOString(),
        readAt: null,
      },
      {
        id: 'n-1004',
        kind: 'AWARD_ISSUED',
        title: 'Notice of Award issued — App app-0203',
        body: 'GMO Reeves signed the Federal award (2 CFR 200.211). Q2 performance report then due 2026-06-30 per 2 CFR 200.328.',
        recipientRole: 'vendor',
        link: '/awards/app-0203',
        createdAt: new Date(Date.now() - 1000 * 60 * 60 * 26).toISOString(),
        readAt: null,
      },
      {
        id: 'n-1005',
        kind: 'OIG_FINDING_OPENED',
        title: 'OIG Finding F-2026-0007 opened',
        body: 'AC-2 access-control finding on award disbursement (2 CFR 200.337) — evidence requested.',
        recipientRole: 'oig_reviewer',
        link: '/admin/findings',
        createdAt: new Date(Date.now() - 1000 * 60 * 60 * 48).toISOString(),
        readAt: new Date(Date.now() - 1000 * 60 * 60 * 47).toISOString(),
      },
    ];
  }
}
