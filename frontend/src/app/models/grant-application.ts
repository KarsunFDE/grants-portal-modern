/**
 * Federal grant application (SF-424 "Application for Federal Assistance" +
 * 2 CFR 200 Uniform Guidance). Reshaped from the inherited acquisition shape
 * to genuine grants fields.
 */
export interface GrantApplication {
  id: string;
  agencyId: string;
  title: string;        // SF-424 Descriptive Title of Applicant's Project
  description: string;  // public project abstract (⚠ rendered raw — Item 9)
  status: string;
  createdAt?: string;
  updatedAt?: string;
  submittedAt?: string;
  // — Grants intake fields (SF-424 / 2 CFR 200) —
  /** NOFO / funding-opportunity number. */
  opportunityNumber?: string;
  /** Assistance Listing Number (CFDA / ALN), e.g., 93.243. */
  assistanceListingNumber?: string;
  /** Awarding agency name, e.g., HHS-NIH, NSF, DOE. */
  awardingAgency?: string;
  /** Applicant organization legal name. */
  applicantOrg?: string;
  /** Applicant SAM Unique Entity ID (12-char; replaced DUNS Apr 2022). */
  applicantUei?: string;
  /** Applicant type (1=Govt, 2=Nonprofit, 3=IHE, …). */
  applicantType?: 'STATE' | 'COUNTY' | 'CITY' | 'NONPROFIT' | 'IHE' | 'INDIVIDUAL' | 'FOR_PROFIT' | 'OTHER';
  /** Principal Investigator / Project Director. */
  principalInvestigator?: string;
  /** Funding instrument per 2 CFR 200. */
  fundingInstrument?: 'GRANT' | 'COOPERATIVE_AGREEMENT';
  /** Federal funds requested (SF-424A). */
  requestedAmountFederal?: number;
  /** Non-federal cost-share / match (SF-424A). */
  costShareMatch?: number;
  /** Areas affected by the project (SF-424 item 14). */
  areasAffected?: string;
  periodOfPerformanceStart?: string;
  periodOfPerformanceEnd?: string;
  /** Narrative / budget-narrative / merit-criteria text keyed sections. */
  sections?: GrantApplicationSections;

  // — Legacy acquisition fields (inherited; pruned by the pair in W4–W5) —
  /** @deprecated acquisition leftover; replaced by assistanceListingNumber. */
  naics?: string;
  /** @deprecated acquisition leftover; replaced by applicantType. */
  setAside?: string;
  /** @deprecated acquisition leftover; replaced by fundingInstrument. */
  contractType?: string;
  /** @deprecated acquisition leftover; replaced by requestedAmountFederal. */
  ceilingValue?: number;
  /** @deprecated acquisition leftover; replaced by opportunityNumber + status. */
  noticeType?: string;
  /** @deprecated acquisition leftover; replaced by periodOfPerformanceEnd. */
  proposalsDueAt?: string;
}

export interface GrantApplicationSections {
  /** Project Narrative / Statement of Need (AI-drafted in wizard). */
  projectNarrative?: string;
  /** Budget Narrative / justification. */
  budgetNarrative?: string;
  /** Merit-review criteria the applicant addresses (significance/approach/feasibility). */
  meritCriteria?: string;
  /** Evaluation / outcomes plan (2 CFR 200.301 performance measurement). */
  evaluationPlan?: string;
}

export interface GrantApplicationCreate {
  agencyId: string;
  title: string;
  description: string;
  status?: string;
  opportunityNumber?: string;
  assistanceListingNumber?: string;
  awardingAgency?: string;
  applicantOrg?: string;
  applicantUei?: string;
  applicantType?: string;
  principalInvestigator?: string;
  fundingInstrument?: string;
  requestedAmountFederal?: number;
  costShareMatch?: number;
  periodOfPerformanceStart?: string;
  periodOfPerformanceEnd?: string;
  sections?: GrantApplicationSections;
}

/** Grants workflow status (2 CFR 200 Subparts C → D). */
export type GrantApplicationState =
  | 'INTAKE'
  | 'SCREENING'
  | 'PEER_REVIEW'
  | 'AWARD_DECISION'
  | 'POST_AWARD_REPORTING'
  | 'CLOSEOUT'
  | 'WITHDRAWN';
