package com.karsunfde.grantsportal.grantapplication.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.UUID;

/**
 * AttachmentService — Principal Investigator file upload for grantApplication
 * supporting documents (CV, budget justification, biosketch, project narrative).
 *
 * Created as a NEW file by `pair-brownfield-generator` per D-059 Step 4b
 * (Cohort #1 Pair 1 — grants-portal-modern). NOT in the acquire-gov baseline.
 *
 * ⚠ DELIBERATE — Pair-unique debt rel-file-upload-local-filesystem (D-059):
 *
 *   {@link #upload(MultipartFile)} writes the uploaded bytes to a local /tmp
 *   path on the container's filesystem. This is single-instance-only — pod
 *   restart loses every attachment; horizontal scaling silently splits
 *   uploads across pods so subsequent GET-by-id randomly 404s.
 *
 *   Fix lands W5 (cloud-native patterns day):
 *     - Replace local-filesystem write with S3 putObject (MinIO locally,
 *       S3 in prod). Bucket already provisioned in infra/docker/docker-compose.yml.
 *     - Return s3:// URI instead of local path.
 *     - {@link #fetch(String)} reads from S3 via getObject.
 *
 *   Discovery path: pair runs the upload endpoint, restarts the service,
 *   tries to GET the attachment by id — 404. The locked-failing test inverts
 *   this — it asserts S3-style return shape.
 */
@Service
public class AttachmentService {

    private static final Logger log = LoggerFactory.getLogger(AttachmentService.class);
    private static final Path UPLOAD_ROOT = Paths.get("/tmp/grant-applications/uploads");

    public AttachmentService() {
        try {
            Files.createDirectories(UPLOAD_ROOT);
        } catch (IOException e) {
            log.warn("could not create local upload dir {}: {}", UPLOAD_ROOT, e.getMessage());
        }
    }

    /**
     * Persist the uploaded file and return its identifier (currently a
     * filesystem path; should be an s3:// URI post-W5).
     *
     * ⚠ Pair-unique debt rel-file-upload-local-filesystem.
     */
    public String upload(MultipartFile file) throws IOException {
        String id = UUID.randomUUID().toString();
        Path target = UPLOAD_ROOT.resolve(id);
        try (InputStream in = file.getInputStream()) {
            Files.copy(in, target, StandardCopyOption.REPLACE_EXISTING);
        }
        log.info("attachment uploaded to local path {} (single-instance only)", target);
        return target.toString();
    }

    /**
     * Resolve an uploaded attachment by id. Returns the local path that
     * {@link #upload(MultipartFile)} produced.
     */
    public Path fetch(String id) {
        return UPLOAD_ROOT.resolve(id);
    }
}
