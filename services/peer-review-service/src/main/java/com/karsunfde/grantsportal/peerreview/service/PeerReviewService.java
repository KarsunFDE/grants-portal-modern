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
 * Merit-review workflow — panel assignment → individual scoring → consensus →
 * funding recommendation → award decision (2 CFR 200.205).
 *
 * Brownfield-debt items reinforced:
 *   - Item 3 — calls grant-application-service for each application's text via
 *     GrantApplicationClient (no circuit breaker).
 *   - Item 2 — state transitions audit-logged via async.
 *   - Item 4 reinforcement — recommendation-draft response from ai-orchestrator
 *     goes straight back; no structured-output schema enforcement.
 */
@Service
public class PeerReviewService {

    private static final Logger log = LoggerFactory.getLogger(PeerReviewService.class);

    private final PeerReviewRepository evalRepo;
    private final PeerReviewScoreRepository scoreRepo;
    private final GrantApplicationClient grantApplicationClient;
    private final AiOrchestratorClient aiClient;
    private final EvalAuditLogger auditLogger;

    @Autowired
    public PeerReviewService(PeerReviewRepository evalRepo,
                             PeerReviewScoreRepository scoreRepo,
                             GrantApplicationClient grantApplicationClient,
                             AiOrchestratorClient aiClient,
                             EvalAuditLogger auditLogger) {
        this.evalRepo = evalRepo;
        this.scoreRepo = scoreRepo;
        this.grantApplicationClient = grantApplicationClient;
        this.aiClient = aiClient;
        this.auditLogger = auditLogger;
    }

    public PeerReview create(String grantApplicationId, String agencyId, String actor) {
        PeerReview e = new PeerReview();
        e.setGrantApplicationId(grantApplicationId);
        e.setAgencyId(agencyId);
        e.setState("OPEN");
        e.setCreatedAt(Instant.now());
        PeerReview saved = evalRepo.save(e);
        auditLogger.recordAsync("EVAL_CREATE", "peerReview", saved.getId(), actor, agencyId);
        return saved;
    }

    public Optional<PeerReview> findById(String id) {
        return evalRepo.findById(id);
    }

    public Optional<PeerReview> assignPanel(String peerReviewId, List<String> panelMembers, String actor) {
        return evalRepo.findById(peerReviewId).map(e -> {
            e.setPanelMembers(panelMembers);
            e.setState("PANEL_ASSIGNED");
            PeerReview saved = evalRepo.save(e);
            auditLogger.recordAsync("EVAL_PANEL_ASSIGN", "peerReview", saved.getId(),
                actor, e.getAgencyId());
            return saved;
        });
    }

    public Optional<PeerReviewScore> submitScore(String peerReviewId, PeerReviewScore in, String actor) {
        Optional<PeerReview> eOpt = evalRepo.findById(peerReviewId);
        if (eOpt.isEmpty()) return Optional.empty();
        PeerReview e = eOpt.get();

        // ⚠ Item 3 — fetches application context from grant-application-service
        // for each score submission. No circuit breaker; under peak merit-review
        // load this is the thread-exhaustion reproducer.
        Map<String, Object> proposal = grantApplicationClient.getGrantApplication(in.getProposalId());
        log.info("score submission peerReviewId={} proposalId={} proposal-loaded={}",
            peerReviewId, in.getProposalId(), proposal != null);

        in.setPeerReviewId(peerReviewId);
        in.setScoredAt(Instant.now());
        PeerReviewScore saved = scoreRepo.save(in);

        // ⚠ Item 2.
        auditLogger.recordAsync("EVAL_SCORE", "score", saved.getId(),
            actor, e.getAgencyId());

        // Promote peerReview state on first score.
        if (!"SCORING".equals(e.getState())) {
            e.setState("SCORING");
            evalRepo.save(e);
        }
        return Optional.of(saved);
    }

    /** Aggregate panel consensus per application × merit criterion. */
    public Map<String, Map<String, Double>> consensus(String peerReviewId) {
        List<PeerReviewScore> scores = scoreRepo.findByPeerReviewId(peerReviewId);
        Map<String, List<PeerReviewScore>> byProposal = scores.stream()
            .collect(Collectors.groupingBy(PeerReviewScore::getProposalId));
        Map<String, Map<String, Double>> out = new LinkedHashMap<>();
        for (Map.Entry<String, List<PeerReviewScore>> p : byProposal.entrySet()) {
            Map<String, Double> byCriterion = p.getValue().stream()
                .collect(Collectors.groupingBy(
                    PeerReviewScore::getMeritCriterionId,
                    Collectors.averagingInt(PeerReviewScore::getScore)));
            out.put(p.getKey(), byCriterion);
        }
        return out;
    }

    /** Draft a panel funding recommendation via ai-orchestrator. */
    public Optional<Map<String, Object>> draftSsdd(String peerReviewId, String actor) {
        return evalRepo.findById(peerReviewId).map(e -> {
            // ⚠ Item 4 reinforcement — raw response returned; no schema check.
            Map<String, Object> resp = aiClient.draftSsdd(peerReviewId);
            e.setState("FUNDING_RECOMMENDATION");
            e.setConsensusAt(Instant.now());
            // Store doc id placeholder from response if present.
            if (resp != null && resp.get("clause_id") != null) {
                e.setSsddDocId(resp.get("clause_id").toString());
            }
            evalRepo.save(e);
            auditLogger.recordAsync("RECOMMENDATION_DRAFT", "peerReview", peerReviewId,
                actor, e.getAgencyId());
            return resp;
        });
    }
}
