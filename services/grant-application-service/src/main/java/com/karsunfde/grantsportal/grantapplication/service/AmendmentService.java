package com.karsunfde.grantsportal.grantapplication.service;

import com.karsunfde.grantsportal.grantapplication.audit.AuditLogger;
import com.karsunfde.grantsportal.grantapplication.dto.AmendmentRequest;
import com.karsunfde.grantsportal.grantapplication.model.Amendment;
import com.karsunfde.grantsportal.grantapplication.model.GrantApplication;
import com.karsunfde.grantsportal.grantapplication.repository.AmendmentRepository;
import com.karsunfde.grantsportal.grantapplication.repository.GrantApplicationRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Amendment issuance (FAR 15.206). Workflow 2.
 *
 * Brownfield-debt items present here:
 *   - Item 2 — amendment publication writes are audit-logged via recordAsync.
 *   - Item 9 — changeSummary stored verbatim.
 *   - Item 10 — list endpoints call findByGrantApplicationId without re-checking
 *     the caller's agency claim against the grantApplication's agency.
 */
@Service
public class AmendmentService {

    private static final Logger log = LoggerFactory.getLogger(AmendmentService.class);

    private final AmendmentRepository repo;
    private final GrantApplicationRepository solRepo;
    private final AuditLogger auditLogger;

    @Autowired
    public AmendmentService(AmendmentRepository repo,
                            GrantApplicationRepository solRepo,
                            AuditLogger auditLogger) {
        this.repo = repo;
        this.solRepo = solRepo;
        this.auditLogger = auditLogger;
    }

    public Optional<Amendment> issue(String grantApplicationId, AmendmentRequest req, String actor) {
        Optional<GrantApplication> solOpt = solRepo.findById(grantApplicationId);
        if (solOpt.isEmpty()) return Optional.empty();
        GrantApplication sol = solOpt.get();

        List<Amendment> existing = repo.findByGrantApplicationIdOrderByNumberAsc(grantApplicationId);
        int nextNumber = existing.isEmpty() ? 1 : existing.get(existing.size() - 1).getNumber() + 1;

        Amendment a = new Amendment();
        a.setGrantApplicationId(grantApplicationId);
        a.setAgencyId(sol.getAgencyId());
        a.setNumber(nextNumber);
        // ⚠ Item 9 — raw HTML stored.
        a.setChangeSummary(req.getChangeSummary());
        a.setRequiresAcknowledgement(req.isRequiresAcknowledgement());
        a.setEffectiveAt(req.getEffectiveAt() != null ? Instant.parse(req.getEffectiveAt()) : Instant.now());
        a.setCreatedAt(Instant.now());
        Amendment saved = repo.save(a);

        // ⚠ Item 2 — fire-and-forget.
        auditLogger.recordAsync("AMEND", "amendment", saved.getId(), actor, sol.getAgencyId());

        log.info("amendment issued grantApplicationId={} number={} agencyId={}",
            grantApplicationId, nextNumber, sol.getAgencyId());

        return Optional.of(saved);
    }

    public List<Amendment> listForGrantApplication(String grantApplicationId) {
        // ⚠ Item 10 — does not re-check caller's agency claim.
        return repo.findByGrantApplicationIdOrderByNumberAsc(grantApplicationId);
    }
}
