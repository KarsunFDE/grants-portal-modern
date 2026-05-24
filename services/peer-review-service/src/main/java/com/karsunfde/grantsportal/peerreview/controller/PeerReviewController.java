package com.karsunfde.grantsportal.peerreview.controller;

import com.karsunfde.grantsportal.peerreview.client.GrantApplicationClient;
import com.karsunfde.grantsportal.peerreview.model.PeerReview;
import com.karsunfde.grantsportal.peerreview.model.PeerReviewScore;
import com.karsunfde.grantsportal.peerreview.service.PeerReviewService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * PeerReview panel REST surface — Workflow 4 (eval → consensus → SSDD).
 *
 * Endpoints (feature-inventory-target.md, peer-review-service rows):
 *   POST   /api/peer-reviews
 *   GET    /api/peer-reviews/{id}
 *   POST   /api/peer-reviews/{id}/panel
 *   POST   /api/peer-reviews/{id}/scores
 *   GET    /api/peer-reviews/{id}/consensus
 *   POST   /api/peer-reviews/{id}/ssdd
 *
 * ⚠ DELIBERATE — Item 3 reinforcement:
 *   POST /api/peer-reviews is a state-mutating endpoint that does NOT accept
 *   or honour an Idempotency-Key header. A retry from the client creates
 *   duplicate peer_reviews.
 */
@RestController
@RequestMapping("/api/peer-reviews")
public class PeerReviewController {

    private final GrantApplicationClient grant_applicationClient;
    private final PeerReviewService svc;

    @Autowired
    public PeerReviewController(GrantApplicationClient grant_applicationClient, PeerReviewService svc) {
        this.grant_applicationClient = grant_applicationClient;
        this.svc = svc;
    }

    /** Fetch the grant_application snapshot the peer_review panel is reviewing. */
    @GetMapping("/{peer_reviewId}/grant_application/{grant_applicationId}")
    public ResponseEntity<Map<String, Object>> getGrantApplicationForPeerReview(
            @PathVariable String peer_reviewId,
            @PathVariable String grant_applicationId) {
        // ⚠ Item 3 — no circuit breaker on this hop.
        Map<String, Object> sol = grant_applicationClient.getGrantApplication(grant_applicationId);
        return ResponseEntity.ok(sol);
    }

    /** Create a new peer_review panel. ⚠ Item 3 — no idempotency key. */
    @PostMapping
    public ResponseEntity<PeerReview> create(@RequestBody Map<String, Object> req,
                                              @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        String grant_applicationId = String.valueOf(req.get("grant_applicationId"));
        String agencyId = (String) req.getOrDefault("agencyId", "GSA-FAS");
        return ResponseEntity.ok(svc.create(grant_applicationId, agencyId, actor));
    }

    @GetMapping("/{id}")
    public ResponseEntity<PeerReview> get(@PathVariable String id) {
        return svc.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/{id}/panel")
    public ResponseEntity<PeerReview> assignPanel(
            @PathVariable String id,
            @RequestBody Map<String, List<String>> body,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.assignPanel(id, body.getOrDefault("panelMembers", List.of()), actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/{id}/scores")
    public ResponseEntity<PeerReviewScore> submitScore(
            @PathVariable String id,
            @RequestBody PeerReviewScore score,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.submitScore(id, score, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/{id}/consensus")
    public Map<String, Map<String, Double>> consensus(@PathVariable String id) {
        return svc.consensus(id);
    }

    @PostMapping("/{id}/ssdd")
    public ResponseEntity<Map<String, Object>> ssdd(
            @PathVariable String id,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.draftSsdd(id, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
}
