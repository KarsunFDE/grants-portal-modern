package com.karsunfde.grantsportal.peerreview.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Merit-review panel record for a grant application (2 CFR 200.205 — review
 * of merit of proposals). A panel of peer reviewers scores the application
 * against published merit criteria, attests to absence of conflict of
 * interest, and produces a funding recommendation.
 *
 * State: OPEN → PANEL_ASSIGNED → SCORING → CONSENSUS → FUNDING_RECOMMENDATION
 *        → AWARD_DECISION / WITHDRAWN.
 * ⚠ Item 3 — fetching application text for scoring is the canonical reproducer
 * for the no-circuit-breaker debt (reviewer → grant-application-service hot loop).
 */
@Document(collection = "peerReviews")
public class PeerReview {

    @Id
    private String id;

    private String grantApplicationId;
    private String agencyId;
    private String state;
    /** Reviewer user IDs assigned to this panel. */
    private List<String> panelMembers = new ArrayList<>();
    /** Published merit-criteria IDs this panel scores against (2 CFR 200.204). */
    private List<String> meritCriteriaIds = new ArrayList<>();
    /** Consensus merit-criterion → averaged score. */
    private Map<String, Double> meritCriteriaScores = new HashMap<>();
    /** Weighted consensus score across criteria. */
    private Double overallScore;
    /** FUND / FUND_WITH_CONDITIONS / DO_NOT_FUND. */
    private String recommendation;
    private String narrativeComments;
    /** Every panel member attested no conflict of interest (2 CFR 200.112). */
    private boolean conflictOfInterestAttested;
    private Instant createdAt;
    private Instant consensusAt;
    /**
     * Optional reference to a generated recommendation document. (Inherited
     * field retained for the Award edge-entity link the pair prunes in W4–W5.)
     */
    private String ssddDocId;

    public PeerReview() {}

    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getGrantApplicationId() { return grantApplicationId; }
    public void setGrantApplicationId(String grantApplicationId) { this.grantApplicationId = grantApplicationId; }
    public String getAgencyId() { return agencyId; }
    public void setAgencyId(String agencyId) { this.agencyId = agencyId; }
    public String getState() { return state; }
    public void setState(String state) { this.state = state; }
    public List<String> getPanelMembers() { return panelMembers; }
    public void setPanelMembers(List<String> panelMembers) { this.panelMembers = panelMembers; }
    public List<String> getMeritCriteriaIds() { return meritCriteriaIds; }
    public void setMeritCriteriaIds(List<String> meritCriteriaIds) { this.meritCriteriaIds = meritCriteriaIds; }
    public Map<String, Double> getMeritCriteriaScores() { return meritCriteriaScores; }
    public void setMeritCriteriaScores(Map<String, Double> meritCriteriaScores) { this.meritCriteriaScores = meritCriteriaScores; }
    public Double getOverallScore() { return overallScore; }
    public void setOverallScore(Double overallScore) { this.overallScore = overallScore; }
    public String getRecommendation() { return recommendation; }
    public void setRecommendation(String recommendation) { this.recommendation = recommendation; }
    public String getNarrativeComments() { return narrativeComments; }
    public void setNarrativeComments(String narrativeComments) { this.narrativeComments = narrativeComments; }
    public boolean isConflictOfInterestAttested() { return conflictOfInterestAttested; }
    public void setConflictOfInterestAttested(boolean conflictOfInterestAttested) { this.conflictOfInterestAttested = conflictOfInterestAttested; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
    public Instant getConsensusAt() { return consensusAt; }
    public void setConsensusAt(Instant consensusAt) { this.consensusAt = consensusAt; }
    public String getSsddDocId() { return ssddDocId; }
    public void setSsddDocId(String ssddDocId) { this.ssddDocId = ssddDocId; }
}
