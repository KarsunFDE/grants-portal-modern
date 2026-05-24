package com.karsunfde.grantsportal.grantapplication.controller;

import com.karsunfde.grantsportal.grantapplication.model.Amendment;
import com.karsunfde.grantsportal.grantapplication.model.GrantApplication;
import com.karsunfde.grantsportal.grantapplication.service.AmendmentService;
import com.karsunfde.grantsportal.grantapplication.service.GrantApplicationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Public SAM.gov-style opportunity search. Anonymous read surface.
 *
 * ⚠ Item 1 — this is the path the gateway's JwtSignatureSkipFilter accepts
 *   unsigned JWTs on.
 * ⚠ Item 9 — opportunity detail renders description verbatim.
 * ⚠ Item 10 — listing crosses agency lines (intentional for "public" but
 *   reinforces the leak pattern).
 */
@RestController
@RequestMapping("/api/public/opportunities")
public class PublicOpportunitiesController {

    private final GrantApplicationService svc;
    private final AmendmentService amendmentSvc;

    @Autowired
    public PublicOpportunitiesController(GrantApplicationService svc,
                                          AmendmentService amendmentSvc) {
        this.svc = svc;
        this.amendmentSvc = amendmentSvc;
    }

    /** SAM.gov-style facet filters (naics, setAside, agency, posted-date). */
    @GetMapping
    public List<GrantApplication> list(@RequestParam(required = false) String naics,
                                    @RequestParam(required = false) String setAside,
                                    @RequestParam(required = false) String agency) {
        // ⚠ Item 10 — public listing always crosses tenants; cohort sees the
        // same pattern in private list endpoints (which is the actual bug).
        return svc.listAll().stream()
            .filter(s -> "PUBLISHED".equals(s.getStatus()) || "AMENDED".equals(s.getStatus()))
            .filter(s -> naics == null || naics.equals(s.getNaics()))
            .filter(s -> setAside == null || setAside.equals(s.getSetAside()))
            .filter(s -> agency == null || agency.equals(s.getAgencyId()))
            .collect(Collectors.toList());
    }

    /** Public opportunity detail. ⚠ Item 9 — description rendered raw. */
    @GetMapping("/{id}")
    public ResponseEntity<Map<String, Object>> detail(@PathVariable String id) {
        return svc.findById(id).map(s -> {
            Map<String, Object> body = new HashMap<>();
            body.put("grant_application", s);
            List<Amendment> amendments = amendmentSvc.listForGrantApplication(id);
            body.put("amendments", amendments);
            return ResponseEntity.ok(body);
        }).orElse(ResponseEntity.notFound().build());
    }
}
