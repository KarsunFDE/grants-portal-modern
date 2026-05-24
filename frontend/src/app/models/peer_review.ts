/**
 * TEP (Technical PeerReview Panel) data model (FAR 15.305).
 *
 * Each evaluator scores each proposal against each Section M factor.
 * Consensus aggregates panel scores; SSA signs SSDD (FAR 15.308 — Source
 * Selection Decision authority cannot delegate).
 */
export interface PeerReviewFactor {
  id: string;
  name: string;
  weight: number;                  // 0–100, sums to 100 across factors
  /** Section M reference, e.g. "M.3.1 Technical Approach" */
  sectionM: string;
}

export interface PeerReviewScore {
  evaluatorId: string;
  evaluatorName: string;
  proposalId: string;
  factorId: string;
  /** 0–10 numeric or color rating; using 0–10 here, displayed as adjectival. */
  score: number;
  narrative: string;
  submittedAt: string;
}

export type PeerReviewState =
  | 'PANEL_ASSIGNMENT'
  | 'INDIVIDUAL_SCORING'
  | 'CONSENSUS'
  | 'SSDD_DRAFT'
  | 'AWAITING_SSA_SIGNATURE'
  | 'AWARDED';

export interface PeerReview {
  id: string;
  grant_applicationId: string;
  panelMembers: string[];          // evaluator user IDs
  factors: PeerReviewFactor[];
  state: PeerReviewState;
  ssddDocId: string | null;
}
