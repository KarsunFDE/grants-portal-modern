package com.karsunfde.grantsportal.grantapplication.service;

import com.karsunfde.grantsportal.grantapplication.audit.AuditLogger;
import com.karsunfde.grantsportal.grantapplication.dto.ProposalSubmitRequest;
import com.karsunfde.grantsportal.grantapplication.model.Proposal;
import com.karsunfde.grantsportal.grantapplication.model.GrantApplication;
import com.karsunfde.grantsportal.grantapplication.repository.ProposalRepository;
import com.karsunfde.grantsportal.grantapplication.repository.GrantApplicationRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * Proposal intake + sealed-lockbox workflow (Workflow 3).
 *
 * Brownfield-debt items present here:
 *   - Item 2 — unseal is multi-step; race with crash can leave the unseal
 *     event un-audited.
 *   - Item 10 — list endpoints do not enforce per-vendor agency boundary.
 */
@Service
public class ProposalService {

    private static final Logger log = LoggerFactory.getLogger(ProposalService.class);

    private final ProposalRepository repo;
    private final GrantApplicationRepository solRepo;
    private final AuditLogger auditLogger;

    @Autowired
    public ProposalService(ProposalRepository repo,
                           GrantApplicationRepository solRepo,
                           AuditLogger auditLogger) {
        this.repo = repo;
        this.solRepo = solRepo;
        this.auditLogger = auditLogger;
    }

    public Optional<Proposal> submit(String grantApplicationId, ProposalSubmitRequest req, String actor) {
        Optional<GrantApplication> solOpt = solRepo.findById(grantApplicationId);
        if (solOpt.isEmpty()) return Optional.empty();
        GrantApplication sol = solOpt.get();

        Proposal p = new Proposal();
        p.setGrantApplicationId(grantApplicationId);
        p.setAgencyId(sol.getAgencyId());
        p.setVendorId(req.getVendorId());
        p.setVolumes(req.getVolumes());
        p.setAcknowledgedAmendments(req.getAcknowledgedAmendments());
        p.setStatus("SEALED");
        p.setSubmittedAt(Instant.now());
        p.setSealedUntil(sol.getPeriodOfPerformanceEnd());
        Proposal saved = repo.save(p);

        // ⚠ Item 2.
        auditLogger.recordAsync("PROPOSAL_SUBMIT", "proposal", saved.getId(),
            actor, sol.getAgencyId());

        log.info("proposal submitted grantApplicationId={} vendorId={}",
            grantApplicationId, req.getVendorId());
        return Optional.of(saved);
    }

    /**
     * Vendor-side endpoint to acknowledge an amendment for a proposal-in-progress
     * (FAR 15.206 — vendors must re-acknowledge after scope-changing amendments).
     */
    public Optional<Proposal> acknowledgeAmendment(String proposalId, int amendmentNumber, String actor) {
        return repo.findById(proposalId).map(p -> {
            if (!p.getAcknowledgedAmendments().contains(amendmentNumber)) {
                p.getAcknowledgedAmendments().add(amendmentNumber);
            }
            Proposal saved = repo.save(p);
            // ⚠ Item 2.
            auditLogger.recordAsync("PROPOSAL_ACK_AMEND", "proposal",
                saved.getId(), actor, p.getAgencyId());
            return saved;
        });
    }

    public List<Proposal> listForGrantApplication(String grantApplicationId) {
        // ⚠ Item 10 — should re-check the caller's agency.
        return repo.findByGrantApplicationId(grantApplicationId);
    }

    public List<Proposal> listForVendor(String vendorId) {
        return repo.findByVendorId(vendorId);
    }
}
