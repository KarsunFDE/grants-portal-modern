package com.karsunfde.grantsportal.grantapplication;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.yaml.snakeyaml.Yaml;

import java.io.InputStream;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Locked-failing test for pair-unique debt item rel-db-pool-size-one
 * (D-059, Cohort #1 Pair 1 — grants-portal-modern).
 *
 * Convention: assertion = what-true-after-modernization.
 *
 * While debt is locked: src/main/resources/application.yml declares
 *   spring.datasource.hikari.maximum-pool-size: 1
 * Every concurrent request serializes through that single connection.
 *
 * Rather than spin up a full @SpringBootTest + drive 10 parallel HTTP calls
 * (heavy + Mongo-dependent), the locked-failing test inspects the YAML
 * directly. After W5 AIOps fix, the cohort raises the pool size (≥10) +
 * sets minimum-idle. Test PASSES then.
 *
 * Single AssertJ assertion — debt observable from config-bytes.
 */
@Tag("brownfield_debt")
@Tag("brownfield_debt_pair_unique_rel_db_pool_size_one")
class DbPoolSizeOneDebtTest {

    @Test
    @SuppressWarnings("unchecked")
    void hikariPoolSizeIsProductionGrade_DEBT_LOCKED() throws Exception {
        try (InputStream is = getClass().getResourceAsStream("/application.yml")) {
            assertThat(is).as("application.yml must be on classpath").isNotNull();

            Map<String, Object> root = new Yaml().load(is);
            Map<String, Object> spring = (Map<String, Object>) root.get("spring");
            Map<String, Object> datasource = (Map<String, Object>) spring.get("datasource");
            Map<String, Object> hikari = (Map<String, Object>) datasource.get("hikari");
            Integer poolSize = (Integer) hikari.get("maximum-pool-size");

            // EXPECTED-AFTER-FIX: pool size ≥ 10 (cohort raises to 20 per
            // fixed_looks_like; floor 10 keeps the assertion robust to
            // alternative production targets).
            assertThat(poolSize)
                .as("Pair-unique debt rel-db-pool-size-one: HikariCP "
                    + "maximum-pool-size must be ≥ 10 for production. "
                    + "Fix lands W5 (AIOps load-testing day).")
                .isGreaterThanOrEqualTo(10);
        }
    }
}
