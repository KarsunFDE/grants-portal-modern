package com.karsunfde.grantsportal.peerreview.model;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/**
 * Source-selection PeerReview panel record. FAR 15.305.
 *
 * State: OPEN → PANEL_ASSIGNED → SCORING → CONSENSUS → AWARDED / CANCELLED.
 * ⚠ Item 3 — fetching proposal text for scoring is the canonical reproducer
 * for the no-circuit-breaker debt (evaluator → grant-application-service hot loop).
 */
@Document(collection = "peerReviews")
public class PeerReview {

    @Id
    private String id;

    private String grantApplicationId;
    private String agencyId;
    private String state;
    private List<String> panelMembers = new ArrayList<>();
    private List<String> factorIds = new ArrayList<>();
    private Instant createdAt;
    private Instant consensusAt;
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
    public List<String> getFactorIds() { return factorIds; }
    public void setFactorIds(List<String> factorIds) { this.factorIds = factorIds; }
    public Instant getCreatedAt() { return createdAt; }
    public void setCreatedAt(Instant createdAt) { this.createdAt = createdAt; }
    public Instant getConsensusAt() { return consensusAt; }
    public void setConsensusAt(Instant consensusAt) { this.consensusAt = consensusAt; }
    public String getSsddDocId() { return ssddDocId; }
    public void setSsddDocId(String ssddDocId) { this.ssddDocId = ssddDocId; }
}
