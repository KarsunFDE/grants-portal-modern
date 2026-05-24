package com.karsunfde.grantsportal.grantapplication.repository;

import com.karsunfde.grantsportal.grantapplication.model.Qna;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface QnaRepository extends MongoRepository<Qna, String> {

    List<Qna> findByGrantApplicationId(String grantApplicationId);

    /** ⚠ Item 10 — declared but unused. */
    List<Qna> findByAgencyId(String agencyId);
}
