package com.karsunfde.grantsportal.peerreview.service;

import com.karsunfde.grantsportal.peerreview.audit.EvalAuditLogger;
import com.karsunfde.grantsportal.peerreview.client.AiOrchestratorClient;
import com.karsunfde.grantsportal.peerreview.client.GrantApplicationClient;
import com.karsunfde.grantsportal.peerreview.model.PeerReview;
import com.karsunfde.grantsportal.peerreview.model.PeerReviewScore;
import com.karsunfde.grantsportal.peerreview.repository.PeerReviewRepository;
import com.karsunfde.grantsportal.peerreview.repository.PeerReviewScoreRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

/**
 * Workflow 4 — peer_review → consensus → source selection → award (pre-award).
 *
 * Brownfield-debt items reinforced:
 *   - Item 3 — calls grant-application-service for each proposal text via
 *     GrantApplicationClient (no circuit breaker).
 *   - Item 2 — state transitions audit-logged via async.
 *   - Item 4 reinforcement — SSDD draft response from ai-orchestrator goes
 *     straight back; no structured-output schema enforcement.
 */
@Service
public class PeerReviewService {

    private static final Logger log = LoggerFactory.getLogger(PeerReviewService.class);

    private final PeerReviewRepository evalRepo;
    private final PeerReviewScoreRepository scoreRepo;
    private final GrantApplicationClient grant_applicationClient;
    private final AiOrchestratorClient aiClient;
    private final EvalAuditLogger auditLogger;

    @Autowired
    public PeerReviewService(PeerReviewRepository evalRepo,
                             PeerReviewScoreRepository scoreRepo,
                             GrantApplicationClient grant_applicationClient,
                             AiOrchestratorClient aiClient,
                             EvalAuditLogger auditLogger) {
        this.evalRepo = evalRepo;
        this.scoreRepo = scoreRepo;
        this.grant_applicationClient = grant_applicationClient;
        this.aiClient = aiClient;
        this.auditLogger = auditLogger;
    }

    public PeerReview create(String grant_applicationId, String agencyId, String actor) {
        PeerReview e = new PeerReview();
        e.setGrantApplicationId(grant_applicationId);
        e.setAgencyId(agencyId);
        e.setState("OPEN");
        e.setCreatedAt(Instant.now());
        PeerReview saved = evalRepo.save(e);
        auditLogger.recordAsync("EVAL_CREATE", "peer_review", saved.getId(), actor, agencyId);
        return saved;
    }

    public Optional<PeerReview> findById(String id) {
        return evalRepo.findById(id);
    }

    public Optional<PeerReview> assignPanel(String peer_reviewId, List<String> panelMembers, String actor) {
        return evalRepo.findById(peer_reviewId).map(e -> {
            e.setPanelMembers(panelMembers);
            e.setState("PANEL_ASSIGNED");
            PeerReview saved = evalRepo.save(e);
            auditLogger.recordAsync("EVAL_PANEL_ASSIGN", "peer_review", saved.getId(),
                actor, e.getAgencyId());
            return saved;
        });
    }

    public Optional<PeerReviewScore> submitScore(String peer_reviewId, PeerReviewScore in, String actor) {
        Optional<PeerReview> eOpt = evalRepo.findById(peer_reviewId);
        if (eOpt.isEmpty()) return Optional.empty();
        PeerReview e = eOpt.get();

        // ⚠ Item 3 — fetches proposal context from grant-application-service for
        // each score submission. No circuit breaker; under TEP-week load
        // this is the thread-exhaustion reproducer.
        Map<String, Object> proposal = grant_applicationClient.getGrantApplication(in.getProposalId());
        log.info("score submission peer_reviewId={} proposalId={} proposal-loaded={}",
            peer_reviewId, in.getProposalId(), proposal != null);

        in.setPeerReviewId(peer_reviewId);
        in.setScoredAt(Instant.now());
        PeerReviewScore saved = scoreRepo.save(in);

        // ⚠ Item 2.
        auditLogger.recordAsync("EVAL_SCORE", "score", saved.getId(),
            actor, e.getAgencyId());

        // Promote peer_review state on first score.
        if (!"SCORING".equals(e.getState())) {
            e.setState("SCORING");
            evalRepo.save(e);
        }
        return Optional.of(saved);
    }

    /** Aggregate panel consensus per proposal × factor. */
    public Map<String, Map<String, Double>> consensus(String peer_reviewId) {
        List<PeerReviewScore> scores = scoreRepo.findByPeerReviewId(peer_reviewId);
        Map<String, List<PeerReviewScore>> byProposal = scores.stream()
            .collect(Collectors.groupingBy(PeerReviewScore::getProposalId));
        Map<String, Map<String, Double>> out = new LinkedHashMap<>();
        for (Map.Entry<String, List<PeerReviewScore>> p : byProposal.entrySet()) {
            Map<String, Double> byFactor = p.getValue().stream()
                .collect(Collectors.groupingBy(
                    PeerReviewScore::getFactorId,
                    Collectors.averagingInt(PeerReviewScore::getScore)));
            out.put(p.getKey(), byFactor);
        }
        return out;
    }

    /** Generate Source Selection Decision Document via ai-orchestrator. */
    public Optional<Map<String, Object>> draftSsdd(String peer_reviewId, String actor) {
        return evalRepo.findById(peer_reviewId).map(e -> {
            // ⚠ Item 4 reinforcement — raw response returned; no schema check.
            Map<String, Object> resp = aiClient.draftSsdd(peer_reviewId);
            e.setState("CONSENSUS");
            e.setConsensusAt(Instant.now());
            // Store doc id placeholder from response if present.
            if (resp != null && resp.get("clause_id") != null) {
                e.setSsddDocId(resp.get("clause_id").toString());
            }
            evalRepo.save(e);
            auditLogger.recordAsync("SSDD_DRAFT", "peer_review", peer_reviewId,
                actor, e.getAgencyId());
            return resp;
        });
    }
}
