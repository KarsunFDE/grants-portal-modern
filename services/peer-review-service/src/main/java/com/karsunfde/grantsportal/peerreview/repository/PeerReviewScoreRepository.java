package com.karsunfde.grantsportal.peerreview.repository;

import com.karsunfde.grantsportal.peerreview.model.PeerReviewScore;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface PeerReviewScoreRepository extends MongoRepository<PeerReviewScore, String> {
    List<PeerReviewScore> findByPeerReviewId(String peer_reviewId);
    List<PeerReviewScore> findByPeerReviewIdAndProposalId(String peer_reviewId, String proposalId);
    List<PeerReviewScore> findByEvaluatorId(String evaluatorId);
}
