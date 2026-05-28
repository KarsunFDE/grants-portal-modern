package com.karsunfde.grantsportal.grantapplication.service;

import com.karsunfde.grantsportal.grantapplication.audit.AuditLogger;
import com.karsunfde.grantsportal.grantapplication.dto.GrantApplicationCreateRequest;
import com.karsunfde.grantsportal.grantapplication.model.GrantApplication;
import com.karsunfde.grantsportal.grantapplication.repository.GrantApplicationRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

/**
 * GrantApplication business logic. Grants intake → award lifecycle.
 *
 * Workflow statuses (2 CFR 200 Subparts C → D):
 *   INTAKE -> SCREENING -> PEER_REVIEW -> AWARD_DECISION -> POST_AWARD_REPORTING
 *   -> (CLOSEOUT). WITHDRAWN reachable from any pre-AWARD_DECISION state.
 *
 * Brownfield-debt items present in this class:
 *   - Item 2 — {@link AuditLogger#recordAsync} runs after response flushes.
 *   - Item 9 — description is stored verbatim (no Jsoup.clean).
 *   - Item 10 — listAll calls repo.findAll() not findByAgencyId.
 *
 * Pair-unique debt (D-059, Cohort #1 Pair 1):
 *   - obs-pii-in-info-logs — {@link #create} logs the Principal Investigator's
 *     full name + the last 4 of their SSN at INFO level. FedRAMP MP-6 / AU-2
 *     violation. Adapted from pool bug_sketch's `applicant.getSsn()` to
 *     grants-context fields (PI name + applicant SSN suffix). Cohort fixes
 *     W5 (AIOps governance day) by hashing identifiers + dropping name.
 */
@Service
public class GrantApplicationService {

    private static final Logger log = LoggerFactory.getLogger(GrantApplicationService.class);

    private final GrantApplicationRepository repo;
    private final AuditLogger auditLogger;

    @Autowired
    public GrantApplicationService(GrantApplicationRepository repo, AuditLogger auditLogger) {
        this.repo = repo;
        this.auditLogger = auditLogger;
    }

    public GrantApplication create(GrantApplicationCreateRequest req, String actor) {
        GrantApplication s = new GrantApplication();
        s.setAgencyId(req.getAgencyId());
        s.setTitle(req.getTitle());
        // ⚠ Item 9 — no Jsoup.clean, no escape, no length cap.
        s.setDescription(req.getDescription());
        s.setStatus(req.getStatus() != null ? req.getStatus() : "INTAKE");
        s.setOpportunityNumber(req.getOpportunityNumber());
        s.setAssistanceListingNumber(req.getAssistanceListingNumber());
        s.setAwardingAgency(req.getAwardingAgency());
        s.setApplicantOrg(req.getApplicantOrg());
        s.setApplicantUei(req.getApplicantUei());
        s.setApplicantType(req.getApplicantType());
        s.setFundingInstrument(req.getFundingInstrument());
        s.setRequestedAmountFederal(req.getRequestedAmountFederal());
        s.setCostShareMatch(req.getCostShareMatch());
        if (req.getPrincipalInvestigatorName() != null) {
            s.setPrincipalInvestigator(req.getPrincipalInvestigatorName());
        }
        s.setCreatedAt(Instant.now());
        s.setUpdatedAt(Instant.now());

        GrantApplication saved = repo.save(s);

        // ⚠ Item 2 — fire-and-forget. Returns immediately, controller flushes
        //   response, audit may or may not land.
        auditLogger.recordAsync("CREATE", "grantApplication", saved.getId(),
            actor, saved.getAgencyId());

        log.info("grantApplication created id={} agencyId={} correlationId=N/A",
            saved.getId(), saved.getAgencyId());

        // ⚠ DELIBERATE — Pair-unique debt obs-pii-in-info-logs (D-059):
        //   Principal Investigator name + last-4 of applicant SSN logged at
        //   INFO. Visible in Datadog / CloudWatch / OTel logs. FedRAMP MP-6
        //   + AU-2 violation. Cohort fixes W5 (AIOps governance day).
        String piName = req.getPrincipalInvestigatorName();
        String ssn = req.getApplicantSsn();
        if (piName != null && ssn != null && ssn.length() >= 4) {
            log.info("PI {} (SSN suffix: {}) submitted grantApplication {}",
                piName, ssn.substring(ssn.length() - 4), saved.getId());
        }

        return saved;
    }

    public Optional<GrantApplication> findById(String id) {
        return repo.findById(id);
    }

    /**
     * ⚠ Item 10 — returns grantApplications across ALL agencies. The
     * {@code findByAgencyId} method exists on the repository but isn't
     * called from anywhere.
     */
    public List<GrantApplication> listAll() {
        return repo.findAll();
    }

    public Optional<GrantApplication> update(String id, GrantApplicationCreateRequest req, String actor) {
        return repo.findById(id).map(s -> {
            s.setTitle(req.getTitle());
            // ⚠ Item 9.
            s.setDescription(req.getDescription());
            if (req.getStatus() != null) s.setStatus(req.getStatus());
            s.setUpdatedAt(Instant.now());
            GrantApplication saved = repo.save(s);
            auditLogger.recordAsync("UPDATE", "grantApplication", saved.getId(),
                actor, saved.getAgencyId());
            return saved;
        });
    }

    public boolean delete(String id, String actor) {
        return repo.findById(id).map(s -> {
            repo.deleteById(id);
            auditLogger.recordAsync("DELETE", "grantApplication", id, actor, s.getAgencyId());
            return true;
        }).orElse(false);
    }

    /**
     * Submit a completed application for eligibility/completeness screening.
     * INTAKE -> SCREENING (2 CFR 200.205). ⚠ Item 2 — submit event
     * audit-logged async.
     */
    public Optional<GrantApplication> publish(String id, String actor) {
        return repo.findById(id).map(s -> {
            s.setStatus("SCREENING");
            s.setSubmittedAt(Instant.now());
            s.setUpdatedAt(Instant.now());
            GrantApplication saved = repo.save(s);
            // ⚠ Item 2.
            auditLogger.recordAsync("SUBMIT", "grantApplication", saved.getId(),
                actor, saved.getAgencyId());
            log.info("grantApplication submitted for screening id={} agencyId={}",
                saved.getId(), saved.getAgencyId());
            return saved;
        });
    }

    /** Applicant withdraws (or agency rejects at screening). */
    public Optional<GrantApplication> cancel(String id, String actor) {
        return repo.findById(id).map(s -> {
            s.setStatus("WITHDRAWN");
            s.setUpdatedAt(Instant.now());
            GrantApplication saved = repo.save(s);
            // ⚠ Item 2.
            auditLogger.recordAsync("WITHDRAW", "grantApplication", saved.getId(),
                actor, saved.getAgencyId());
            return saved;
        });
    }
}
