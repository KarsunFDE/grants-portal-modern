package com.karsunfde.grantsportal.grantapplication.controller;

import com.karsunfde.grantsportal.grantapplication.dto.AmendmentRequest;
import com.karsunfde.grantsportal.grantapplication.dto.ProposalSubmitRequest;
import com.karsunfde.grantsportal.grantapplication.dto.QnaAnswerRequest;
import com.karsunfde.grantsportal.grantapplication.dto.QnaRequest;
import com.karsunfde.grantsportal.grantapplication.dto.GrantApplicationCreateRequest;
import com.karsunfde.grantsportal.grantapplication.model.Amendment;
import com.karsunfde.grantsportal.grantapplication.model.Proposal;
import com.karsunfde.grantsportal.grantapplication.model.Qna;
import com.karsunfde.grantsportal.grantapplication.model.GrantApplication;
import com.karsunfde.grantsportal.grantapplication.service.AmendmentService;
import com.karsunfde.grantsportal.grantapplication.service.ProposalService;
import com.karsunfde.grantsportal.grantapplication.service.QnaService;
import com.karsunfde.grantsportal.grantapplication.service.GrantApplicationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * GrantApplication REST surface — covers Workflow 1 (drafting → publication),
 * Workflow 2 (Q&A + amendments), Workflow 3 (proposal intake).
 *
 * Endpoints (feature-inventory-target.md, grant-application-service rows):
 *   POST    /api/grant-applications
 *   GET     /api/grant-applications
 *   GET     /api/grant-applications/{id}
 *   PUT     /api/grant-applications/{id}
 *   DELETE  /api/grant-applications/{id}
 *   POST    /api/grant-applications/{id}/publish
 *   POST    /api/grant-applications/{id}/cancel
 *   POST    /api/grant-applications/{id}/amendments
 *   GET     /api/grant-applications/{id}/amendments
 *   POST    /api/grant-applications/{id}/qa
 *   PUT     /api/grant-applications/{id}/qa/{qnaId}/answer
 *   GET     /api/grant-applications/{id}/qa
 *   POST    /api/grant-applications/{id}/proposals
 *   GET     /api/grant-applications/{id}/proposals
 *   POST    /api/grant-applications/{id}/proposals/{pid}/acknowledge-amendment
 */
@RestController
@RequestMapping("/api/grant-applications")
public class GrantApplicationController {

    private final GrantApplicationService svc;
    private final AmendmentService amendmentSvc;
    private final QnaService qnaSvc;
    private final ProposalService proposalSvc;

    @Autowired
    public GrantApplicationController(GrantApplicationService svc,
                                  AmendmentService amendmentSvc,
                                  QnaService qnaSvc,
                                  ProposalService proposalSvc) {
        this.svc = svc;
        this.amendmentSvc = amendmentSvc;
        this.qnaSvc = qnaSvc;
        this.proposalSvc = proposalSvc;
    }

    @GetMapping
    public List<GrantApplication> list(@RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        // ⚠ Item 10 — does not filter by agency.
        return svc.listAll();
    }

    @GetMapping("/{id}")
    public ResponseEntity<GrantApplication> get(@PathVariable String id) {
        return svc.findById(id)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping
    public ResponseEntity<GrantApplication> create(
            @RequestBody GrantApplicationCreateRequest req,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        // ⚠ Item 9 — no validation on req.description.
        GrantApplication created = svc.create(req, actor);
        return ResponseEntity.ok(created);
    }

    @PutMapping("/{id}")
    public ResponseEntity<GrantApplication> update(
            @PathVariable String id,
            @RequestBody GrantApplicationCreateRequest req,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.update(id, req, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(
            @PathVariable String id,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        boolean ok = svc.delete(id, actor);
        return ok ? ResponseEntity.noContent().build() : ResponseEntity.notFound().build();
    }

    // -------- State machine transitions (Workflow 1) --------

    @PostMapping("/{id}/publish")
    public ResponseEntity<GrantApplication> publish(
            @PathVariable String id,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.publish(id, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PostMapping("/{id}/cancel")
    public ResponseEntity<GrantApplication> cancel(
            @PathVariable String id,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return svc.cancel(id, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    // -------- Amendments (Workflow 2 — FAR 15.206) --------

    @PostMapping("/{id}/amendments")
    public ResponseEntity<Amendment> issueAmendment(
            @PathVariable String id,
            @RequestBody AmendmentRequest req,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return amendmentSvc.issue(id, req, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/{id}/amendments")
    public List<Amendment> listAmendments(@PathVariable String id) {
        // ⚠ Item 10 — does not re-check caller agency.
        return amendmentSvc.listForGrantApplication(id);
    }

    // -------- Q&A (Workflow 2) --------

    @PostMapping("/{id}/qa")
    public ResponseEntity<Qna> submitQuestion(
            @PathVariable String id,
            @RequestBody QnaRequest req,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return qnaSvc.submit(id, req, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @PutMapping("/{id}/qa/{qnaId}/answer")
    public ResponseEntity<Qna> answer(
            @PathVariable String id,
            @PathVariable String qnaId,
            @RequestBody QnaAnswerRequest req,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return qnaSvc.answer(qnaId, req, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/{id}/qa")
    public List<Qna> listQna(@PathVariable String id) {
        // ⚠ Item 10 — vendor should only see their own pre-publish entries.
        return qnaSvc.listForGrantApplication(id);
    }

    // -------- Proposal intake (Workflow 3) --------

    @PostMapping("/{id}/proposals")
    public ResponseEntity<Proposal> submitProposal(
            @PathVariable String id,
            @RequestBody ProposalSubmitRequest req,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return proposalSvc.submit(id, req, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }

    @GetMapping("/{id}/proposals")
    public List<Proposal> listProposals(@PathVariable String id) {
        // ⚠ Item 2 — must be gated on post-deadline + audit-logged on view.
        // ⚠ Item 10 — does not re-check caller agency.
        return proposalSvc.listForGrantApplication(id);
    }

    @PostMapping("/{id}/proposals/{pid}/acknowledge-amendment")
    public ResponseEntity<Proposal> acknowledgeAmendment(
            @PathVariable String id,
            @PathVariable("pid") String proposalId,
            @RequestParam("amendmentNumber") int amendmentNumber,
            @RequestHeader(value = "X-User", defaultValue = "anonymous") String actor) {
        return proposalSvc.acknowledgeAmendment(proposalId, amendmentNumber, actor)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
}
