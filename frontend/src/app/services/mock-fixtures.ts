/**
 * Instructor-demo fixtures.
 *
 * The grants-portal-modern backend endpoints listed in feature-inventory-target.md
 * are scaffold-level; many return empty or 404 against the current
 * legacy stack. To keep instructor-driven demos showing realistic
 * federal grants-management data even without a fully populated DB, every
 * page falls back to these fixtures on HTTP error.
 *
 * Realism citations (all retrieved 2026-05-28 via /web-research):
 *   - SF-424 "Application for Federal Assistance" field set (opportunity #,
 *     Assistance Listing / CFDA, applicant UEI, applicant type)
 *   - Grants.gov NOFO record shape (opportunity number convention)
 *   - 2 CFR 200 Uniform Guidance (funding instrument, period of performance,
 *     merit review §200.205, post-award reporting §200.328-329)
 *
 * NOTE: Vendor / Award / Cpar / ContractModification / Deliverable fixtures
 * below are inherited acquisition-edge demo data the pair repurposes or
 * deletes in W4–W5 modernization (see domain-mapping.md "Additional inherited
 * entities"). Left intact so edge components still render.
 */

import { GrantApplication, GrantApplicationState } from '../models/grant-application';
import { Amendment } from '../models/amendment';
import { Qna } from '../models/qna';
import { Proposal } from '../models/proposal';
import { PeerReview, PeerReviewScore } from '../models/peer-review';
import { Award, ContractModification, Deliverable, Cpar } from '../models/award';
import { Vendor } from '../models/vendor';
import { AuditEvent } from '../models/audit';
import { Finding } from '../models/finding';

export const FIXTURE_SOLICITATIONS: GrantApplication[] = [
  {
    id: 'app-0142',
    agencyId: 'HHS-ACF',
    title: 'Community Health Worker Capacity-Building in Rural Clinics',
    description: 'Expands the community health worker workforce across 11 rural counties to improve preventive-care access for underserved populations.',
    status: 'PEER_REVIEW' as GrantApplicationState,
    opportunityNumber: 'HHS-2026-ACF-OCS-EE-0142',
    assistanceListingNumber: '93.243',
    awardingAgency: 'HHS-ACF',
    applicantOrg: 'Appalachian Regional Health Coalition',
    applicantUei: 'AB1CDE2FGHI3',
    applicantType: 'NONPROFIT',
    principalInvestigator: 'Dr. Maria Alvarez',
    fundingInstrument: 'GRANT',
    requestedAmountFederal: 1_250_000,
    costShareMatch: 250_000,
    periodOfPerformanceStart: new Date(Date.now() + 1000 * 60 * 60 * 24 * 60).toISOString(),
    periodOfPerformanceEnd: new Date(Date.now() + 1000 * 60 * 60 * 24 * 425).toISOString(),
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 21).toISOString(),
    // legacy mirror (edge dashboards/public browse)
    proposalsDueAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 14).toISOString(),
  },
  {
    id: 'app-0203',
    agencyId: 'NSF',
    title: 'Undergraduate Research in Coastal Resilience Modeling',
    description: 'A cooperative agreement establishing a research-experience program training undergraduates in coastal-resilience and sea-level-rise modeling.',
    status: 'PEER_REVIEW' as GrantApplicationState,
    opportunityNumber: 'NSF-26-0203',
    assistanceListingNumber: '47.050',
    awardingAgency: 'NSF',
    applicantOrg: 'State University of Example',
    applicantUei: 'ZX9YWV8UTSR7',
    applicantType: 'IHE',
    principalInvestigator: 'Dr. Samuel Park',
    fundingInstrument: 'COOPERATIVE_AGREEMENT',
    requestedAmountFederal: 600_000,
    costShareMatch: 0,
    periodOfPerformanceStart: new Date(Date.now() + 1000 * 60 * 60 * 24 * 90).toISOString(),
    periodOfPerformanceEnd: new Date(Date.now() + 1000 * 60 * 60 * 24 * 1185).toISOString(),
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 35).toISOString(),
    proposalsDueAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 7).toISOString(),
  },
  {
    id: 'app-0301',
    agencyId: 'DOE',
    title: 'Weatherization Assistance for Low-Income Households',
    description: 'Formula-style weatherization services reducing energy burden for low-income households in three tribal communities.',
    status: 'SCREENING' as GrantApplicationState,
    opportunityNumber: 'DE-FOA-0000301',
    assistanceListingNumber: '81.042',
    awardingAgency: 'DOE',
    applicantOrg: 'Three Rivers Tribal Council',
    applicantUei: 'IN0TECHFGHIJ',
    applicantType: 'OTHER',
    principalInvestigator: 'Joseph Whitefeather',
    fundingInstrument: 'GRANT',
    requestedAmountFederal: 480_000,
    costShareMatch: 48_000,
    periodOfPerformanceStart: new Date(Date.now() + 1000 * 60 * 60 * 24 * 45).toISOString(),
    periodOfPerformanceEnd: new Date(Date.now() + 1000 * 60 * 60 * 24 * 410).toISOString(),
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 9).toISOString(),
  },
  {
    id: 'app-0418',
    agencyId: 'HHS-ACF',
    title: 'Draft — Early Childhood Mentorship Pilot',
    description: 'Pre-submission draft. Completeness review pending.',
    status: 'INTAKE' as GrantApplicationState,
    opportunityNumber: 'HHS-2026-ACF-OCS-EE-0418',
    assistanceListingNumber: '93.600',
    awardingAgency: 'HHS-ACF',
    applicantOrg: 'Bright Futures Nonprofit',
    applicantUei: 'BF7UTURES2026',
    applicantType: 'NONPROFIT',
    principalInvestigator: 'Dr. Lena Okafor',
    fundingInstrument: 'GRANT',
    requestedAmountFederal: 320_000,
    costShareMatch: 32_000,
    createdAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(),
  },
];

export const FIXTURE_AMENDMENTS: Amendment[] = [
  {
    id: 'am-0001',
    grantApplicationId: 'app-0142',
    number: 1,
    changeSummary: 'Add CMMC Level 2 attestation to Section H minimum requirements.',
    effectiveAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5).toISOString(),
    requiresAcknowledgement: true,
    acknowledgedBy: ['vnd-acme', 'vnd-globex'],
    issuedBy: 'co-reeves',
    issuedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5).toISOString(),
  },
  {
    id: 'am-0002',
    grantApplicationId: 'app-0142',
    number: 2,
    changeSummary: 'Extend proposal deadline by 7 days; clarify Section L page limit (60 pages including ToC).',
    effectiveAt: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
    requiresAcknowledgement: true,
    acknowledgedBy: ['vnd-acme'],
    issuedBy: 'co-reeves',
    issuedAt: new Date(Date.now() - 1000 * 60 * 60 * 24).toISOString(),
  },
];

export const FIXTURE_QNA: Qna[] = [
  {
    id: 'qa-001',
    grantApplicationId: 'app-0142',
    question: 'Is the FedRAMP Moderate baseline a hard requirement at proposal submission or by award date?',
    answer: 'FedRAMP Moderate authorization (or In-Process status with completion path documented) is required at proposal submission per Section L.5.2.',
    vendorId: 'vnd-acme',
    postedAt: new Date(Date.now() - 1000 * 60 * 60 * 26).toISOString(),
    publishedAt: new Date(Date.now() - 1000 * 60 * 60 * 22).toISOString(),
    status: 'PUBLISHED',
  },
  {
    id: 'qa-002',
    grantApplicationId: 'app-0142',
    question: 'Can past performance from a parent-company contract be cited?',
    answer: null,
    vendorId: 'vnd-globex',
    postedAt: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
    publishedAt: null,
    status: 'DRAFT_ANSWER',
  },
  {
    id: 'qa-003',
    grantApplicationId: 'app-0142',
    question: 'What is the period of performance start date assumed for Volume III pricing?',
    answer: null,
    vendorId: 'vnd-initech',
    postedAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
    publishedAt: null,
    status: 'NEW',
  },
];

export const FIXTURE_PROPOSALS: Proposal[] = [
  {
    id: 'prop-001',
    grantApplicationId: 'app-0142',
    vendorId: 'vnd-acme',
    vendorName: 'Acme Federal LLC',
    volumes: [
      { volume: 'I_TECHNICAL', attachmentId: 'att-001', pageCount: 58, submittedAt: new Date().toISOString() },
      { volume: 'II_PAST_PERFORMANCE', attachmentId: 'att-002', pageCount: 22, submittedAt: new Date().toISOString() },
      { volume: 'III_PRICE', attachmentId: 'att-003', pageCount: 12, submittedAt: new Date().toISOString() },
    ],
    submittedAt: new Date(Date.now() - 1000 * 60 * 60 * 6).toISOString(),
    sealedUntil: new Date(Date.now() + 1000 * 60 * 60 * 24 * 14).toISOString(),
    amendmentAcks: [1, 2],
  },
  {
    id: 'prop-002',
    grantApplicationId: 'app-0142',
    vendorId: 'vnd-globex',
    vendorName: 'Globex Federal Systems',
    volumes: [
      { volume: 'I_TECHNICAL', attachmentId: 'att-101', pageCount: 60, submittedAt: new Date().toISOString() },
      { volume: 'II_PAST_PERFORMANCE', attachmentId: 'att-102', pageCount: 18, submittedAt: new Date().toISOString() },
      { volume: 'III_PRICE', attachmentId: 'att-103', pageCount: 10, submittedAt: new Date().toISOString() },
    ],
    submittedAt: new Date(Date.now() - 1000 * 60 * 60 * 3).toISOString(),
    sealedUntil: new Date(Date.now() + 1000 * 60 * 60 * 24 * 14).toISOString(),
    amendmentAcks: [1],
  },
  {
    id: 'prop-003',
    grantApplicationId: 'app-0142',
    vendorId: 'vnd-initech',
    vendorName: 'Initech Cloud Services',
    volumes: [
      { volume: 'I_TECHNICAL', attachmentId: 'att-201', pageCount: 55, submittedAt: new Date().toISOString() },
      { volume: 'II_PAST_PERFORMANCE', attachmentId: 'att-202', pageCount: 20, submittedAt: new Date().toISOString() },
      { volume: 'III_PRICE', attachmentId: 'att-203', pageCount: 11, submittedAt: new Date().toISOString() },
    ],
    submittedAt: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
    sealedUntil: new Date(Date.now() + 1000 * 60 * 60 * 24 * 14).toISOString(),
    amendmentAcks: [],
  },
];

export const FIXTURE_EVALUATION: PeerReview = {
  id: 'eval-0142',
  grantApplicationId: 'app-0142',
  panelMembers: ['rv-allen', 'rv-mendez', 'rv-park'],
  criteria: [
    { id: 'c-sig', name: 'Significance', weight: 40, description: 'Importance of the problem and project impact' },
    { id: 'c-app', name: 'Approach', weight: 30, description: 'Soundness of design, methods, and work plan' },
    { id: 'c-feas', name: 'Feasibility / Investigator', weight: 20, description: 'Capacity and qualifications to execute' },
    { id: 'c-budget', name: 'Budget reasonableness', weight: 10, description: 'Costs allowable, allocable, reasonable (2 CFR 200 Subpart E)' },
  ],
  state: 'INDIVIDUAL_SCORING',
  overallScore: 8.1,
  recommendation: 'FUND_WITH_CONDITIONS',
  conflictOfInterestAttested: true,
  ssddDocId: null,
};

export const FIXTURE_SCORES: PeerReviewScore[] = [
  { reviewerId: 'rv-allen', reviewerName: 'Dr. Allen', proposalId: 'app-0142', meritCriterionId: 'c-sig', score: 9, narrative: 'Addresses a well-documented rural-health access gap.', submittedAt: new Date().toISOString() },
  { reviewerId: 'rv-allen', reviewerName: 'Dr. Allen', proposalId: 'app-0203', meritCriterionId: 'c-sig', score: 7, narrative: 'Significant but narrower geographic impact.', submittedAt: new Date().toISOString() },
  { reviewerId: 'rv-mendez', reviewerName: 'A. Mendez', proposalId: 'app-0142', meritCriterionId: 'c-app', score: 8, narrative: 'Clear logic model; measurable objectives and evaluation plan.', submittedAt: new Date().toISOString() },
  { reviewerId: 'rv-mendez', reviewerName: 'A. Mendez', proposalId: 'app-0203', meritCriterionId: 'c-app', score: 8, narrative: 'Strong methodology; mentorship structure well defined.', submittedAt: new Date().toISOString() },
];

export const FIXTURE_AWARD: Award = {
  id: 'aw-2026-001',
  peerReviewId: 'eval-0142',
  grantApplicationId: 'app-0142',
  winningVendorId: 'vnd-acme',
  winningVendorName: 'Acme Federal LLC',
  contractNumber: 'GS-35F-0001V',
  awardedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 30).toISOString(),
  ceilingValue: 110_000_000,
  debriefDeadline: new Date(Date.now() - 1000 * 60 * 60 * 24 * 25).toISOString(),
};

export const FIXTURE_MODIFICATIONS: ContractModification[] = [
  { id: 'mod-001', contractId: 'ctr-0001', modNumber: 'P00001', type: 'bilateral', changeDescription: 'Option year 1 exercise; ceiling delta +$18M.', effectiveAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 200).toISOString(), signedBy: 'co-reeves' },
  { id: 'mod-002', contractId: 'ctr-0001', modNumber: 'A00001', type: 'unilateral', changeDescription: 'Administrative — updated POC email after PM transition.', effectiveAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 120).toISOString(), signedBy: 'co-reeves' },
];

export const FIXTURE_DELIVERABLES: Deliverable[] = [
  { id: 'del-001', contractId: 'ctr-0001', cdrlNumber: 'A001', title: 'Monthly Status Report — May 2026', dueAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 5).toISOString(), status: 'PENDING', acceptedBy: null },
  { id: 'del-002', contractId: 'ctr-0001', cdrlNumber: 'A002', title: 'Q2 Security Compliance Attestation', dueAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 3).toISOString(), status: 'SUBMITTED', acceptedBy: null },
  { id: 'del-003', contractId: 'ctr-0001', cdrlNumber: 'A003', title: 'Annual Cost Baseline Refresh', dueAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 14).toISOString(), status: 'ACCEPTED', acceptedBy: 'co-reeves' },
];

export const FIXTURE_CPARS: Cpar[] = [
  {
    id: 'cpar-001',
    contractId: 'ctr-0001',
    period: 'INTERIM',
    ratings: [
      { factor: 'QUALITY', rating: 'VERY_GOOD', narrative: 'Deliverables consistently meet acceptance criteria.' },
      { factor: 'SCHEDULE', rating: 'SATISFACTORY', narrative: 'Two CDRLs slipped by less than 5 days each.' },
      { factor: 'COST_CONTROL', rating: 'VERY_GOOD', narrative: 'Burn rate within 3% of baseline.' },
      { factor: 'MANAGEMENT', rating: 'EXCEPTIONAL', narrative: 'Proactive risk communication; subcontractor mgmt strong.' },
      { factor: 'SMALL_BUSINESS', rating: 'SATISFACTORY', narrative: 'Met 23% small-business subcontracting target.' },
      { factor: 'REGULATORY_COMPLIANCE', rating: 'VERY_GOOD', narrative: 'FedRAMP continuous monitoring up to date.' },
    ],
    overallNarrative: 'Strong interim performance; ready to exercise option year 2.',
    vendorRebuttal: null,
    rebuttalDeadline: new Date(Date.now() + 1000 * 60 * 60 * 24 * 45).toISOString(),
    status: 'AWAITING_VENDOR_REVIEW',
  },
];

export const FIXTURE_VENDORS: Vendor[] = [
  {
    id: 'vnd-acme',
    duns: '123456789',
    uei: 'AB1CDE2FGHI3',
    cage: '7XYZ4',
    name: 'Acme Federal LLC',
    naicsCodes: ['541512', '541519'],
    setAsides: ['SMALL_BUSINESS', '8A'],
    registeredAt: '2018-04-12T00:00:00Z',
    pastPerformanceAvg: { exceptional: 4, veryGood: 11, satisfactory: 6, marginal: 1, unsatisfactory: 0, totalReports: 22 },
  },
  {
    id: 'vnd-globex',
    duns: '987654321',
    uei: 'ZX9YWV8UTSR7',
    cage: '4ABC2',
    name: 'Globex Federal Systems',
    naicsCodes: ['541511', '541512'],
    setAsides: ['FULL_AND_OPEN' as never],
    registeredAt: '2014-09-01T00:00:00Z',
    pastPerformanceAvg: { exceptional: 2, veryGood: 8, satisfactory: 12, marginal: 3, unsatisfactory: 1, totalReports: 26 },
  },
  {
    id: 'vnd-initech',
    duns: '555111222',
    uei: 'IN0TECHFGHIJ',
    cage: '9PQR5',
    name: 'Initech Cloud Services',
    naicsCodes: ['541519'],
    setAsides: ['SDVOSB'],
    registeredAt: '2020-01-15T00:00:00Z',
    pastPerformanceAvg: { exceptional: 0, veryGood: 3, satisfactory: 5, marginal: 2, unsatisfactory: 0, totalReports: 10 },
  },
];

export const FIXTURE_AUDIT_EVENTS: AuditEvent[] = [
  { id: 'ae-001', actorId: 'po-reeves', actorName: 'Dana Reeves', agencyId: 'HHS-ACF', action: 'APPLICATION.SUBMIT', objectType: 'GrantApplication', objectId: 'app-0142', correlationId: 'r-abc-001', before: { status: 'INTAKE' }, after: { status: 'SCREENING' }, ts: new Date(Date.now() - 1000 * 60 * 60 * 24 * 7).toISOString() },
  { id: 'ae-002', actorId: 'co-reeves', actorName: 'Dana Reeves', agencyId: 'GSA-FAS', action: 'AMENDMENT.ISSUE', objectType: 'Amendment', objectId: 'am-0001', correlationId: 'r-abc-002', before: null, after: { number: 1 }, ts: new Date(Date.now() - 1000 * 60 * 60 * 24 * 5).toISOString() },
  { id: 'ae-003', actorId: 'cs-ortiz', actorName: 'Miguel Ortiz', agencyId: 'GSA-FAS', action: 'QNA.ANSWER', objectType: 'Qna', objectId: 'qa-001', correlationId: 'r-def-001', before: { status: 'AWAITING_CO_APPROVAL' }, after: { status: 'PUBLISHED' }, ts: new Date(Date.now() - 1000 * 60 * 60 * 22).toISOString() },
  { id: 'ae-004', actorId: 'ssa-whitfield', actorName: 'Col. Whitfield', agencyId: 'GSA-FAS', action: 'SSDD.SIGN', objectType: 'PeerReview', objectId: 'eval-0142', correlationId: 'r-ghi-001', before: { state: 'AWAITING_SSA_SIGNATURE' }, after: { state: 'AWARDED' }, ts: new Date(Date.now() - 1000 * 60 * 60 * 24 * 30).toISOString() },
];

export const FIXTURE_FINDINGS: Finding[] = [
  {
    id: 'F-2026-0007',
    scope: 'PLATFORM',
    scopeId: 'grants-portal-modern',
    title: 'CI lint workflow disabled — repo-self finding',
    findingType: 'CA-7 continuous monitoring',
    severity: 'MODERATE',
    status: 'OPEN',
    openedBy: 'oig-park',
    openedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(),
    remediationDueAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 30).toISOString(),
    evidenceRequests: [
      { id: 'er-1', requestedBy: 'oig-park', requestedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 2).toISOString(), description: 'Provide screenshot of re-enabled lint step in successful PR build.', fulfilledAt: null },
    ],
    description: 'Repository CI (`infra/github-actions/ci.yml`) skips lint with TODO. (Item 12 — meta-mirror per feature inventory.)',
  },
  {
    id: 'F-2026-0008',
    scope: 'CONTRACT',
    scopeId: 'ctr-0001',
    title: 'QASP findings ledger missing 2 entries for May surveillance',
    findingType: 'AU-12 audit record generation',
    severity: 'HIGH',
    status: 'IN_REMEDIATION',
    openedBy: 'oig-park',
    openedAt: new Date(Date.now() - 1000 * 60 * 60 * 24 * 14).toISOString(),
    remediationDueAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 10).toISOString(),
    evidenceRequests: [],
    description: 'AuditEvent gap suggests Item 2 race during high-load surveillance window.',
  },
];
