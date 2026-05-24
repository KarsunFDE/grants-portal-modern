package com.karsunfde.grantsportal.peerreview.repository;

import com.karsunfde.grantsportal.peerreview.model.DebriefRequest;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface DebriefRequestRepository extends MongoRepository<DebriefRequest, String> {
    List<DebriefRequest> findByAwardId(String awardId);
}
