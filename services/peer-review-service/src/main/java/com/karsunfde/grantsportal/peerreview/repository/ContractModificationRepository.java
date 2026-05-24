package com.karsunfde.grantsportal.peerreview.repository;

import com.karsunfde.grantsportal.peerreview.model.ContractModification;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface ContractModificationRepository extends MongoRepository<ContractModification, String> {
    List<ContractModification> findByContractIdOrderByModNumberAsc(String contractId);
}
