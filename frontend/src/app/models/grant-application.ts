export interface GrantApplication {
  id: string;
  agencyId: string;
  title: string;
  description: string;
  status: string;
  createdAt?: string;
  updatedAt?: string;
  // — Expanded fields (multi-step drafting wizard, FAR 15.204 Sections A–M)
  naics?: string;
  setAside?: '' | 'SDVOSB' | 'WOSB' | 'HUBZONE' | '8A' | 'SMALL_BUSINESS' | 'FULL_AND_OPEN';
  contractType?: 'FFP' | 'CPFF' | 'T_AND_M' | 'IDIQ' | 'BPA';
  ceilingValue?: number;
  /** GrantApplication type per FAR Subpart 15.2 / SAM.gov categories. */
  noticeType?: 'RFI' | 'SOURCES_SOUGHT' | 'RFP' | 'RFQ' | 'COMBINED_SYNOPSIS';
  /** Section content keyed by FAR 15.204 part: A through M (skipping I per convention). */
  sections?: GrantApplicationSections;
  /** ISO timestamp; vendors locked at this time. */
  proposalsDueAt?: string;
}

export interface GrantApplicationSections {
  sectionA?: string;  // GrantApplication/Contract Form
  sectionB?: string;  // Supplies/Services + Prices/Costs
  sectionC?: string;  // Statement of Work (AI-drafted in wizard)
  sectionD?: string;  // Packaging and Marking
  sectionE?: string;  // Inspection and Acceptance
  sectionF?: string;  // Deliveries or Performance
  sectionG?: string;  // Contract Administration Data
  sectionH?: string;  // Special Contract Requirements
  sectionJ?: string;  // List of Attachments
  sectionK?: string;  // Reps + Certs
  sectionL?: string;  // Instructions to Offerors (AI-drafted in wizard)
  sectionM?: string;  // PeerReview Factors
}

export interface GrantApplicationCreate {
  agencyId: string;
  title: string;
  description: string;
  status?: string;
  naics?: string;
  setAside?: string;
  contractType?: string;
  ceilingValue?: number;
  noticeType?: string;
  sections?: GrantApplicationSections;
  proposalsDueAt?: string;
}

/** Workflow 1 state machine (feature-inventory-target.md). */
export type GrantApplicationState =
  | 'DRAFT'
  | 'INTERNAL_REVIEW'
  | 'READY_TO_PUBLISH'
  | 'PUBLISHED'
  | 'AMENDED'
  | 'CLOSED'
  | 'CANCELLED';
