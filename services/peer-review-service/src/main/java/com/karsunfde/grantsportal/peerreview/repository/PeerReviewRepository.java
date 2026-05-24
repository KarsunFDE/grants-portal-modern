package com.karsunfde.grantsportal.peerreview.repository;

import com.karsunfde.grantsportal.peerreview.model.PeerReview;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface PeerReviewRepository extends MongoRepository<PeerReview, String> {
    List<PeerReview> findByGrantApplicationId(String grant_applicationId);
    /** ⚠ Item 10 — declared but list endpoints often skip. */
    List<PeerReview> findByAgencyId(String agencyId);
}
