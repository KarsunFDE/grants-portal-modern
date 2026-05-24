package com.karsunfde.grantsportal.peerreview.repository;

import com.karsunfde.grantsportal.peerreview.model.Finding;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface FindingRepository extends MongoRepository<Finding, String> {
    List<Finding> findByRemediationStatus(String status);
    List<Finding> findByContractId(String contractId);
}
