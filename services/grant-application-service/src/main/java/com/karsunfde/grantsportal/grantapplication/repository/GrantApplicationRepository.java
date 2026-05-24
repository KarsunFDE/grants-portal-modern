package com.karsunfde.grantsportal.grantapplication.repository;

import com.karsunfde.grantsportal.grantapplication.model.GrantApplication;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

/**
 * ⚠ DELIBERATE — Item 10:
 *   {@code findAll()} returns grantApplications across ALL agencies. There is a
 *   {@code findByAgencyId} method declared below — it just isn't called from
 *   {@code GrantApplicationService}. Cohort fixes in W2 Wed by switching all
 *   reads to {@code findByAgencyId} (and resolving agency from JWT).
 */
public interface GrantApplicationRepository extends MongoRepository<GrantApplication, String> {

    /** Declared but not used — the cohort discovers and wires this up. */
    List<GrantApplication> findByAgencyId(String agencyId);
}
