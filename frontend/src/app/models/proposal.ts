/**
 * Vendor proposal volumes (FAR 15.204).
 *
 * Sealed in MongoDB GridFS until grantApplication deadline. Post-deadline,
 * CO unseals (atomic + audit-logged — touches Item 2 race surface).
 */
export interface ProposalVolume {
  volume: 'I_TECHNICAL' | 'II_PAST_PERFORMANCE' | 'III_PRICE';
  attachmentId: string;
  pageCount: number;
  submittedAt: string;
}

export interface Proposal {
  id: string;
  grantApplicationId: string;
  vendorId: string;
  vendorName: string;
  volumes: ProposalVolume[];
  submittedAt: string;
  sealedUntil: string;             // ISO — grantApplication deadline
  amendmentAcks: number[];         // acknowledged amendment numbers
}
