package com.karsunfde.grantsportal.grantapplication.notification;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * No-op notification fan-out. Stand-in for SendGrid v1 SDK + in-app push.
 * Real wiring deferred to W6 deliverability work.
 *
 * 5 notification surfaces per feature-inventory-target.md:
 *   1. GrantApplication published → registered vendors (NAICS-matched)
 *   2. Amendment issued → vendors with proposals-in-progress
 *   3. Proposal received → CO + CS
 *   4. PeerReview due in 7d → assigned evaluators
 *   5. Award decision → winning + unsuccessful offerors
 *   6. Contract anniversary (CPAR window opens) → PM
 *
 * Brownfield-debt items present here:
 *   - Item 2 — notification dispatch is fire-and-forget, separate from
 *     audit. The "amendment issued" path can complete-then-crash leaving
 *     the audit row dropped.
 *   - Item 5 — copy generation for CPAR-window notification calls the
 *     legacy LangChain path (see legacy_chain.py in ai-orchestrator).
 *   - Item 6 — no correlation-ID threaded into the notification log.
 *   - Item 10 — "registered vendors" matcher ignores agency_id; can leak
 *     a grantApplication notice to vendors outside the issuing agency.
 */
@Component
public class Notifier {

    private static final Logger log = LoggerFactory.getLogger(Notifier.class);

    public void grantApplicationPublished(String grantApplicationId, String agencyId,
                                       String naics, List<String> vendorEmails) {
        // ⚠ Item 10 — vendorEmails is computed without agency_id filter
        // upstream; cohort discovers in W4 Wed.
        log.info("notify[PUBLISH] grantApplicationId={} agencyId={} naics={} recipients={}",
            grantApplicationId, agencyId, naics, vendorEmails.size());
    }

    public void amendmentIssued(String grantApplicationId, int amendmentNumber,
                                 List<String> vendorEmails) {
        // ⚠ Item 2 — fire-and-forget; not in the audit transaction.
        log.info("notify[AMEND] grantApplicationId={} amendment={} recipients={}",
            grantApplicationId, amendmentNumber, vendorEmails.size());
    }

    public void proposalReceived(String grantApplicationId, String proposalId,
                                  List<String> agencyEmails) {
        // ⚠ Item 6 — correlation-id not present.
        log.info("notify[PROPOSAL_RX] grantApplicationId={} proposalId={} recipients={}",
            grantApplicationId, proposalId, agencyEmails.size());
    }

    public void peerReviewDue(String peerReviewId, List<String> evaluatorEmails) {
        // ⚠ Item 3 — no retry/circuit on notification dispatch path.
        log.info("notify[EVAL_DUE] peerReviewId={} recipients={}",
            peerReviewId, evaluatorEmails.size());
    }

    public void awardDecision(String awardId, String winningVendorEmail,
                               List<String> losingVendorEmails) {
        // ⚠ Item 9 reinforcement — debrief request narrative will be passed
        // raw to /draft-amendment style copy generator.
        log.info("notify[AWARD] awardId={} winner={} losing-recipients={}",
            awardId, winningVendorEmail, losingVendorEmails.size());
    }

    public void cparWindowOpened(String contractId, String pmEmail) {
        // ⚠ Item 5 — copy generator calls the legacy LLMChain path. This is
        // the 3rd entry point that feeds legacy_chain.py.
        log.info("notify[CPAR_WINDOW] contractId={} recipient={} copy-generator=legacy_chain",
            contractId, pmEmail);
    }
}
