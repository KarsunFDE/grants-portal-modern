package com.karsunfde.grantsportal.grantapplication.controller;

import com.karsunfde.grantsportal.grantapplication.model.ClauseLibraryEntry;
import com.karsunfde.grantsportal.grantapplication.service.ClauseLibraryService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * Clause-library endpoints. Surface for W2 RAG corpus introspection +
 * lexical fallback path.
 */
@RestController
@RequestMapping("/api/clauses")
public class ClauseController {

    private final ClauseLibraryService svc;

    @Autowired
    public ClauseController(ClauseLibraryService svc) {
        this.svc = svc;
    }

    @GetMapping("/search")
    public List<ClauseLibraryEntry> search(@RequestParam(required = false) String q,
                                            @RequestParam(required = false) String farPart) {
        return svc.search(q, farPart);
    }

    @GetMapping("/{clauseId}")
    public ResponseEntity<ClauseLibraryEntry> getByClauseId(@PathVariable String clauseId) {
        return svc.findByClauseId(clauseId)
            .map(ResponseEntity::ok)
            .orElse(ResponseEntity.notFound().build());
    }
}
