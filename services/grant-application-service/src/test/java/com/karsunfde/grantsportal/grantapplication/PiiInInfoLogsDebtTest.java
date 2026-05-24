package com.karsunfde.grantsportal.grantapplication;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.Logger;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import com.karsunfde.grantsportal.grantapplication.audit.AuditLogger;
import com.karsunfde.grantsportal.grantapplication.dto.GrantApplicationCreateRequest;
import com.karsunfde.grantsportal.grantapplication.model.GrantApplication;
import com.karsunfde.grantsportal.grantapplication.repository.GrantApplicationRepository;
import com.karsunfde.grantsportal.grantapplication.service.GrantApplicationService;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;

import java.util.List;
import java.util.stream.Collectors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Locked-failing test for pair-unique debt obs-pii-in-info-logs
 * (D-059, Cohort #1 Pair 1 — grants-portal-modern).
 *
 * Convention: assertion = what-true-after-modernization.
 *
 * While debt is locked: GrantApplicationService.create() logs the PI's full
 * name + last-4 of applicant SSN at INFO. Attach a Logback ListAppender to
 * the service logger, invoke create() with sentinel PII, then inspect the
 * captured messages. Both sentinels must NOT appear after the W5 fix
 * (cohort hashes + drops name).
 *
 * Two AssertJ assertions — observable from logging stream.
 *
 * Adaptation note (per SKILL Step 4b): pool bug_sketch references
 * `applicant.getFullName()` + `applicant.getSsn().substring(5)` on an
 * Applicant entity. Adapted to grants-context fields on the create-request
 * (principalInvestigatorName + applicantSsn). Recorded in
 * domain-mapping.md adaptations log.
 */
@Tag("brownfield_debt")
@Tag("brownfield_debt_pair_unique_obs_pii_in_info_logs")
class PiiInInfoLogsDebtTest {

    @Test
    void infoLogsExcludeIdentifyingPII_DEBT_LOCKED() {
        // Attach a Logback ListAppender to the service logger.
        Logger serviceLogger = (Logger) LoggerFactory.getLogger(GrantApplicationService.class);
        ListAppender<ILoggingEvent> appender = new ListAppender<>();
        appender.start();
        serviceLogger.addAppender(appender);
        serviceLogger.setLevel(Level.INFO);

        GrantApplicationRepository repo = mock(GrantApplicationRepository.class);
        AuditLogger audit = mock(AuditLogger.class);
        when(repo.save(any(GrantApplication.class))).thenAnswer(inv -> {
            GrantApplication g = inv.getArgument(0);
            g.setId("ga-test-1");
            return g;
        });

        GrantApplicationService svc = new GrantApplicationService(repo, audit);

        GrantApplicationCreateRequest req = new GrantApplicationCreateRequest();
        req.setAgencyId("agency-test");
        req.setTitle("Test grantApplication");
        req.setDescription("d");
        req.setStatus("DRAFT");
        req.setPrincipalInvestigatorName("Dr Alice Sentinel-Carver");
        req.setApplicantSsn("111-22-3333");

        svc.create(req, "actor-1");

        List<String> messages = appender.list.stream()
            .map(ILoggingEvent::getFormattedMessage)
            .collect(Collectors.toList());

        // EXPECTED-AFTER-FIX: neither the PI name nor the last-4 of the SSN
        // appears in any INFO-level log message. Currently both do → test
        // fails as expected.
        assertThat(messages)
            .as("Pair-unique debt obs-pii-in-info-logs: PI name must not appear "
                + "in INFO logs (FedRAMP MP-6). Fix lands W5.")
            .noneMatch(m -> m.contains("Sentinel-Carver"));
        assertThat(messages)
            .as("Pair-unique debt obs-pii-in-info-logs: SSN suffix must not appear "
                + "in INFO logs (FedRAMP MP-6). Fix lands W5.")
            .noneMatch(m -> m.contains("3333"));
    }
}
