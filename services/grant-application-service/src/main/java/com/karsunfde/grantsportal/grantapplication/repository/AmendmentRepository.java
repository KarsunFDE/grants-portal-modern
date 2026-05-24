package com.karsunfde.grantsportal.grantapplication.repository;

import com.karsunfde.grantsportal.grantapplication.model.Amendment;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface AmendmentRepository extends MongoRepository<Amendment, String> {

    List<Amendment> findByGrantApplicationIdOrderByNumberAsc(String grantApplicationId);

    /** ⚠ Item 10 — declared but unused. */
    List<Amendment> findByAgencyId(String agencyId);
}
