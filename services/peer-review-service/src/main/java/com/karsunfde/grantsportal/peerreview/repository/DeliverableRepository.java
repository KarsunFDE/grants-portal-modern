package com.karsunfde.grantsportal.peerreview.repository;

import com.karsunfde.grantsportal.peerreview.model.Deliverable;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface DeliverableRepository extends MongoRepository<Deliverable, String> {
    List<Deliverable> findByContractId(String contractId);
}
