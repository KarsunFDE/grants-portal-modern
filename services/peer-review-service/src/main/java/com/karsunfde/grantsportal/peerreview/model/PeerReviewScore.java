package com.karsunfde.grantsportal.peerreview.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;

/**
 * Per-reviewer, per-application, per-merit-criterion score
 * (2 CFR 200.205 merit review).
 */
@Document(collection = "peer_review_scores")
public class PeerReviewScore {

    @Id
    private String id;

    private String peerReviewId;
    private String reviewerId;
    /** Application being scored (this is the proposal/application snapshot id). */
    private String proposalId;
    /** Merit criterion this score applies to (e.g., significance, approach). */
    private String meritCriterionId;
    private int score;       // raw 0-100 or criterion-defined scale
    private String narrative;
    private Instant scoredAt;

    public PeerReviewScore() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getPeerReviewId() { return peerReviewId; }
    public void setPeerReviewId(String peerReviewId) { this.peerReviewId = peerReviewId; }
    public String getReviewerId() { return reviewerId; }
    public void setReviewerId(String reviewerId) { this.reviewerId = reviewerId; }
    public String getProposalId() { return proposalId; }
    public void setProposalId(String proposalId) { this.proposalId = proposalId; }
    public String getMeritCriterionId() { return meritCriterionId; }
    public void setMeritCriterionId(String meritCriterionId) { this.meritCriterionId = meritCriterionId; }
    public int getScore() { return score; }
    public void setScore(int score) { this.score = score; }
    public String getNarrative() { return narrative; }
    public void setNarrative(String narrative) { this.narrative = narrative; }
    public Instant getScoredAt() { return scoredAt; }
    public void setScoredAt(Instant scoredAt) { this.scoredAt = scoredAt; }
}
