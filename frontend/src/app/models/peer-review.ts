/**
 * Merit-review panel data model (2 CFR 200.205 — review of merit of proposals).
 *
 * Each peer reviewer scores the application against published merit criteria
 * (significance, approach, feasibility, …). Consensus aggregates panel scores;
 * the panel issues a funding recommendation (fund / fund-with-conditions /
 * do-not-fund) and each reviewer attests no conflict of interest (2 CFR 200.112).
 */
export interface MeritCriterion {
  id: string;
  name: string;
  weight: number;                  // 0–100, sums to 100 across criteria
  /** Criterion reference, e.g. "Significance" / "Approach" / "Feasibility". */
  description: string;
}

export type FundingRecommendation =
  | 'FUND'
  | 'FUND_WITH_CONDITIONS'
  | 'DO_NOT_FUND';

export interface PeerReviewScore {
  reviewerId: string;
  reviewerName: string;
  proposalId: string;              // application snapshot id
  meritCriterionId: string;
  /** 0–10 numeric rating; displayed as adjectival. */
  score: number;
  narrative: string;
  submittedAt: string;
}

export type PeerReviewState =
  | 'PANEL_ASSIGNMENT'
  | 'INDIVIDUAL_SCORING'
  | 'CONSENSUS'
  | 'FUNDING_RECOMMENDATION'
  | 'AWARD_DECISION'
  | 'WITHDRAWN';

export interface PeerReview {
  id: string;
  grantApplicationId: string;
  panelMembers: string[];          // peer-reviewer user IDs
  criteria: MeritCriterion[];
  state: PeerReviewState;
  overallScore?: number;
  recommendation?: FundingRecommendation;
  conflictOfInterestAttested?: boolean;
  /** Optional reference to a generated recommendation document. */
  ssddDocId: string | null;
}
