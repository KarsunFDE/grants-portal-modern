package com.karsunfde.grantsportal.grantapplication;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;

import javax.servlet.http.HttpServletRequest;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Locked-failing test for pair-unique debt item sec-cors-wildcard-credentials
 * (D-059, Cohort #1 Pair 1 — grants-portal-modern).
 *
 * Convention: assertion = what-true-after-modernization.
 *
 * While debt is locked (current state): SecurityConfig.corsConfig() configures
 * wildcard origin pattern AND allowCredentials = true. CorsConfiguration
 * exposes both flags; this test inspects the bean directly and asserts they
 * are not both permissive at once — a property the fix-state guarantees.
 *
 * After W4 Wed fix:
 *   - setAllowedOrigins(List.of("https://grants-portal.karsun.gov", ...))
 *   - addAllowedOriginPattern("*") removed
 *   - setAllowCredentials(true) retained
 *   - Test PASSES.
 *
 * Single AssertJ assertion — debt observable from CorsConfiguration state.
 */
@Tag("brownfield_debt")
@Tag("brownfield_debt_pair_unique_sec_cors_wildcard_credentials")
class CorsWildcardCredentialsDebtTest {

    @Test
    void corsBeanDoesNotCombineWildcardWithCredentials_DEBT_LOCKED() {
        SecurityConfig config = new SecurityConfig();
        CorsConfigurationSource source = config.corsConfig();

        // Resolve the CorsConfiguration for an arbitrary path. The
        // UrlBasedCorsConfigurationSource registers "/**" — any request maps
        // through.
        HttpServletRequest req = mock(HttpServletRequest.class);
        when(req.getRequestURI()).thenReturn("/api/grant-applications");

        CorsConfiguration cors = source.getCorsConfiguration(req);
        assertThat(cors).as("CORS configuration must resolve for /api/grant-applications").isNotNull();

        boolean usesWildcardPattern =
            cors.getAllowedOriginPatterns() != null
                && cors.getAllowedOriginPatterns().contains("*");
        boolean allowsCredentials =
            Boolean.TRUE.equals(cors.getAllowCredentials());

        // EXPECTED-AFTER-FIX: wildcard origin pattern + credentials must not
        // coexist. Currently both are true → test fails as expected.
        assertThat(usesWildcardPattern && allowsCredentials)
            .as("Pair-unique debt sec-cors-wildcard-credentials: CORS must not "
                + "combine wildcard origin pattern with allowCredentials=true. "
                + "Fix lands W4 Wed (OWASP API01).")
            .isFalse();
    }
}
