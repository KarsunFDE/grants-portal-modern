package com.karsunfde.grantsportal.peerreview.repository;

import com.karsunfde.grantsportal.peerreview.model.Award;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;
import java.util.Optional;

public interface AwardRepository extends MongoRepository<Award, String> {
    Optional<Award> findByPeerReviewId(String peerReviewId);
    /** ⚠ Item 10 — declared but unused. */
    List<Award> findByAgencyId(String agencyId);
}
