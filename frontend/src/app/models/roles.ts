/**
 * Federal grants-management role model.
 *
 * Mirrors the JWT `role` claim defined in feature-inventory-target.md
 * personas table. FedRAMP RBAC AC-2/AC-5 (least-privilege +
 * separation-of-duties). Authority notes cite 2 CFR 200 (Uniform Guidance).
 *
 * The underlying `Role` enum keys are inherited from the acquisition baseline
 * and intentionally unchanged so route guards / `role.guard.ts` stay stable;
 * the cohort renames the enum keys themselves in W4–W5. The grants-facing
 * personas below are mapped onto those keys:
 *   contracting_officer → Grants Management Officer (signs the award)
 *   program_manager     → Program Officer (default; owns the program/NOFO)
 *   evaluator           → Peer Reviewer (merit review)
 *   vendor              → Grantee / Principal Investigator (external applicant)
 *   oig_reviewer        → OIG (audit)
 * `contract_specialist` and `ssa` have no first-class grants equivalent yet and
 * are relabeled as support/legacy personas.
 *
 * NOTE: this is a mock role-switcher for cohort instructor demos.
 * Production RBAC resolves role from validated JWT in the API gateway
 * (which today has Debt Item 1 — JWT signature-skip on `/api/public/*`).
 */
export type Role =
  | 'contracting_officer'
  | 'contract_specialist'
  | 'program_manager'
  | 'ssa'
  | 'evaluator'
  | 'vendor'
  | 'oig_reviewer'
  | 'sys_admin'
  | 'public';

export interface RoleProfile {
  role: Role;
  displayName: string;
  agencyId: string | null;   // null for sys_admin (cross-tenant) and public
  vendorDuns?: string;       // only present for `vendor`
  /** FAR/FedRAMP authority notes shown in role-switcher tooltip. */
  authorityNote: string;
}

export const ROLE_PROFILES: RoleProfile[] = [
  {
    // Program Officer — default persona. Owns the program / NOFO and the
    // pre-award merit-review process (2 CFR 200.205).
    role: 'program_manager',
    displayName: 'Priya Shah (Program Officer, HHS-ACF)',
    agencyId: 'HHS-ACF',
    authorityNote: 'Owns NOFO + program; manages merit review (2 CFR 200.204-205). Cannot sign the Federal award.',
  },
  {
    role: 'contracting_officer',
    displayName: 'Dana Reeves (Grants Management Officer, HHS-ACF)',
    agencyId: 'HHS-ACF',
    authorityNote: 'Signs the Federal award, issues amendments, certifies obligations (2 CFR 200.211 / 200.308).',
  },
  {
    role: 'evaluator',
    displayName: 'Dr. Allen (Peer Reviewer, merit panel)',
    agencyId: 'HHS-ACF',
    authorityNote: 'Scores assigned applications against published merit criteria (2 CFR 200.205). COI attestation required.',
  },
  {
    role: 'vendor',
    displayName: 'Dr. Maria Alvarez (Grantee / PI — Appalachian Regional Health Coalition, UEI AB1CDE2FGHI3)',
    agencyId: null,
    vendorDuns: '123456789',
    authorityNote: 'External applicant: submit SF-424 application; file post-award performance reports (2 CFR 200.328-329).',
  },
  {
    role: 'oig_reviewer',
    displayName: 'Inspector Park (OIG)',
    agencyId: 'HHS-OIG',
    authorityNote: 'Read-only across awarding agencies; open audit findings (2 CFR 200.337).',
  },
  {
    // Support persona — no first-class grants role yet (relabeled from CS).
    role: 'contract_specialist',
    displayName: 'Miguel Ortiz (Grants Specialist, HHS-ACF)',
    agencyId: 'HHS-ACF',
    authorityNote: 'Drafts applications + award packages; cannot sign the Federal award.',
  },
  {
    // Legacy pre-grants authority retained for inherited source-selection surfaces.
    role: 'ssa',
    displayName: 'Col. Whitfield (Selecting Official — legacy pre-grants)',
    agencyId: 'HHS-ACF',
    authorityNote: 'Legacy final-selection authority retained for inherited merit-consensus surface; W4–W5 repurposes.',
  },
  {
    role: 'sys_admin',
    displayName: 'Root (sys_admin)',
    agencyId: null,
    authorityNote: 'Cross-tenant admin; provisioning + key rotation.',
  },
  {
    role: 'public',
    displayName: 'Unauthenticated visitor',
    agencyId: null,
    authorityNote: 'Read-only on /public/* (Item 1 surface).',
  },
];
