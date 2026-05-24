package com.karsunfde.grantsportal.grantapplication;

import com.karsunfde.grantsportal.grantapplication.service.AttachmentService;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Locked-failing test for pair-unique debt rel-file-upload-local-filesystem
 * (D-059, Cohort #1 Pair 1 — grants-portal-modern).
 *
 * Convention: assertion = what-true-after-modernization.
 *
 * While debt is locked: AttachmentService.upload() writes to /tmp and
 * returns a local path. After W5 fix, the implementation puts to S3/MinIO
 * and returns an "s3://" URI. The locked test asserts the S3-style return
 * shape — a property easier to verify than full pod-restart survival.
 *
 * Single AssertJ assertion — debt observable from return-string shape.
 */
@Tag("brownfield_debt")
@Tag("brownfield_debt_pair_unique_rel_file_upload_local_filesystem")
class FileUploadLocalFilesystemDebtTest {

    @Test
    void attachmentReturnsObjectStorageUri_DEBT_LOCKED() throws IOException {
        AttachmentService svc = new AttachmentService();
        MultipartFile file = new MockMultipartFile(
            "biosketch", "biosketch.pdf", "application/pdf",
            "fake pdf bytes".getBytes()
        );

        String returned = svc.upload(file);

        // EXPECTED-AFTER-FIX: identifier is an s3:// URI (or equivalent
        // object-storage URI). Currently it's a local /tmp path → test
        // fails as expected.
        assertThat(returned)
            .as("Pair-unique debt rel-file-upload-local-filesystem: upload "
                + "must persist to object storage (S3/MinIO) and return an "
                + "s3:// URI. Currently returns local filesystem path. Fix "
                + "lands W5 (cloud-native patterns day).")
            .startsWith("s3://");
    }
}
