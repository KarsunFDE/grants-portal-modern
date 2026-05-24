package com.karsunfde.grantsportal.peerreview.repository;

import com.karsunfde.grantsportal.peerreview.model.Cpar;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface CparRepository extends MongoRepository<Cpar, String> {
    List<Cpar> findByContractId(String contractId);
    List<Cpar> findByVendorId(String vendorId);
}
