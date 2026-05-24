package com.karsunfde.grantsportal.grantapplication.service;

import com.karsunfde.grantsportal.grantapplication.audit.AuditLogger;
import com.karsunfde.grantsportal.grantapplication.dto.QnaAnswerRequest;
import com.karsunfde.grantsportal.grantapplication.dto.QnaRequest;
import com.karsunfde.grantsportal.grantapplication.model.Qna;
import com.karsunfde.grantsportal.grantapplication.model.GrantApplication;
import com.karsunfde.grantsportal.grantapplication.repository.QnaRepository;
import com.karsunfde.grantsportal.grantapplication.repository.GrantApplicationRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Vendor Q&A workflow.
 *
 * Brownfield-debt items present here:
 *   - Item 2 — Q&A state transitions audit-logged via recordAsync.
 *   - Item 9 — question + answer stored verbatim; both feed the
 *     ai-orchestrator /answer-qa prompt.
 *   - Item 10 — listForGrantApplication does not re-check agency.
 */
@Service
public class QnaService {

    private static final Logger log = LoggerFactory.getLogger(QnaService.class);

    private final QnaRepository repo;
    private final GrantApplicationRepository solRepo;
    private final AuditLogger auditLogger;

    @Autowired
    public QnaService(QnaRepository repo, GrantApplicationRepository solRepo, AuditLogger auditLogger) {
        this.repo = repo;
        this.solRepo = solRepo;
        this.auditLogger = auditLogger;
    }

    public Optional<Qna> submit(String grant_applicationId, QnaRequest req, String actor) {
        Optional<GrantApplication> solOpt = solRepo.findById(grant_applicationId);
        if (solOpt.isEmpty()) return Optional.empty();
        GrantApplication sol = solOpt.get();

        Qna q = new Qna();
        q.setGrantApplicationId(grant_applicationId);
        q.setAgencyId(sol.getAgencyId());
        // ⚠ Item 9 — raw HTML accepted.
        q.setQuestion(req.getQuestion());
        q.setVendorId(req.getVendorId());
        q.setStatus("SUBMITTED");
        q.setSubmittedAt(Instant.now());
        Qna saved = repo.save(q);

        // ⚠ Item 2 — fire-and-forget.
        auditLogger.recordAsync("QNA_SUBMIT", "qna", saved.getId(), actor, sol.getAgencyId());

        log.info("qna submitted grant_applicationId={} vendorId={}", grant_applicationId, req.getVendorId());
        return Optional.of(saved);
    }

    public Optional<Qna> answer(String qnaId, QnaAnswerRequest req, String actor) {
        return repo.findById(qnaId).map(q -> {
            // ⚠ Item 9.
            q.setAnswer(req.getAnswer());
            q.setStatus("PUBLISHED");
            q.setAnsweredAt(Instant.now());
            Qna saved = repo.save(q);
            // ⚠ Item 2.
            auditLogger.recordAsync("QNA_ANSWER", "qna", saved.getId(), actor, q.getAgencyId());
            return saved;
        });
    }

    public List<Qna> listForGrantApplication(String grant_applicationId) {
        // ⚠ Item 10 — does not re-check caller agency.
        return repo.findByGrantApplicationId(grant_applicationId);
    }
}
