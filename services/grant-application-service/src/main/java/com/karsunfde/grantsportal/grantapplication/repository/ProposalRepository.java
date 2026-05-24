package com.karsunfde.grantsportal.grantapplication.repository;

import com.karsunfde.grantsportal.grantapplication.model.Proposal;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface ProposalRepository extends MongoRepository<Proposal, String> {

    List<Proposal> findByGrantApplicationId(String grantApplicationId);

    /** ⚠ Item 10 — vendors should NOT see other vendors' proposals; this
     *  method is the safe one but isn't always used. */
    List<Proposal> findByVendorId(String vendorId);

    /** ⚠ Item 10 — declared but unused. */
    List<Proposal> findByAgencyId(String agencyId);
}
