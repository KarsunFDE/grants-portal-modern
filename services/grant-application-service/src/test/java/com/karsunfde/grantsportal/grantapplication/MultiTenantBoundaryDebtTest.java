package com.karsunfde.grantsportal.grantapplication;

import com.karsunfde.grantsportal.grantapplication.audit.AuditLogger;
import com.karsunfde.grantsportal.grantapplication.repository.GrantApplicationRepository;
import com.karsunfde.grantsportal.grantapplication.service.GrantApplicationService;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Locked-failing test for brownfield-debt item 10
 * (no-multi-tenant-boundary in grant-application-service).
 *
 * Convention (see fde-10-week/pipeline/T27-debt-enforcement-spec.md):
 *   While the debt is present, GrantApplicationService.listAll() calls
 *   repo.findAll() — an unfiltered cross-agency query. After W2-Wed
 *   multi-tenant-retrieval-boundary modernization, listAll() routes through
 *   repo.findByAgencyId(currentAgency) and never invokes findAll(). This
 *   test asserts the post-fix invariant; while debt is locked, it FAILS.
 *
 * Single Mockito verify() assertion — the locked state is observable by
 * watching which repository method the service calls.
 */
@Tag("brownfield_debt")
@Tag("brownfield_debt_10")
class MultiTenantBoundaryDebtTest {

    @Test
    void listAll_does_not_call_unfiltered_findAll_DEBT_LOCKED() {
        GrantApplicationRepository repo = mock(GrantApplicationRepository.class);
        AuditLogger audit = mock(AuditLogger.class);
        when(repo.findAll()).thenReturn(List.of());
        when(repo.findByAgencyId(anyString())).thenReturn(List.of());
        GrantApplicationService svc = new GrantApplicationService(repo, audit);

        svc.listAll();

        // EXPECTED-AFTER-FIX: listAll routes through findByAgencyId, never
        // through findAll. While debt locked: GrantApplicationService.listAll()
        // returns repo.findAll() -> verify(never()) fails as expected.
        verify(repo, never()).findAll();
    }
}
