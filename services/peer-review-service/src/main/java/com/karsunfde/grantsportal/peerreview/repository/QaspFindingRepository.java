package com.karsunfde.grantsportal.peerreview.repository;

import com.karsunfde.grantsportal.peerreview.model.QaspFinding;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface QaspFindingRepository extends MongoRepository<QaspFinding, String> {
    List<QaspFinding> findByContractId(String contractId);
}
