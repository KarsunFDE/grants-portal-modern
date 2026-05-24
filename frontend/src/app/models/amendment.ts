/**
 * Amendment to a published grantApplication (FAR 15.206).
 *
 * Numbered sequentially per grantApplication. Issuance is restricted to CO.
 * Vendors with proposals-in-progress must acknowledge before deadline;
 * acknowledgement state is tracked here.
 */
export interface Amendment {
  id: string;
  grantApplicationId: string;
  number: number;                  // 0001, 0002, ...
  changeSummary: string;
  effectiveAt: string;             // ISO
  requiresAcknowledgement: boolean;
  acknowledgedBy: string[];        // vendor IDs
  issuedBy: string;                // CO user id
  issuedAt: string;                // ISO
}

export interface AmendmentCreate {
  changeSummary: string;
  effectiveAt: string;
  requiresAcknowledgement: boolean;
}
