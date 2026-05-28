/**
 * In-app notification (bell + drawer surface).
 *
 * Source events mapped in feature-inventory-target.md notification
 * surfaces table. Item 6 (inconsistent correlation IDs) bites because
 * the notification log uses a different correlation ID than the
 * originating service request.
 */
export type NotificationKind =
  // Grants-management kinds (2 CFR 200 Uniform Guidance lifecycle).
  | 'NOFO_PUBLISHED'
  | 'APPLICATION_RECEIVED'
  | 'MERIT_REVIEW_DUE'
  | 'AWARD_ISSUED'
  | 'PERFORMANCE_REPORT_DUE'
  | 'OIG_FINDING_OPENED'
  // Legacy pre-grants acquisition kinds — retained for inherited surfaces
  // that still reference them; not emitted on grants events.
  | 'SOLICITATION_PUBLISHED'
  | 'AMENDMENT_ISSUED'
  | 'PROPOSAL_RECEIVED'
  | 'EVALUATION_DUE'
  | 'AWARD_DECISION'
  | 'CPAR_WINDOW_OPEN'
  | 'QASP_FINDING'
  | 'DEBRIEF_REQUESTED';

export interface Notification {
  id: string;
  kind: NotificationKind;
  title: string;
  body: string;
  recipientRole: string;
  link: string;                    // router link
  createdAt: string;               // ISO
  readAt: string | null;
}
