CREATE TABLE source_evidence (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_sha256 VARCHAR(64) NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    source_name VARCHAR(160) NOT NULL,
    provider VARCHAR(160) NOT NULL,
    declared_region VARCHAR(160) NOT NULL,
    authorization_reference VARCHAR(300) NOT NULL,
    verification_status VARCHAR(40) NOT NULL,
    created_by VARCHAR(80) NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_source_evidence_sha256 (source_sha256)
);

ALTER TABLE operation_revision ADD COLUMN source_evidence_id BIGINT NULL;
ALTER TABLE operation_revision ADD COLUMN source_row_no INT NULL;
ALTER TABLE operation_revision ADD COLUMN source_verification_status VARCHAR(40) NOT NULL DEFAULT 'LEGACY_UNVERIFIED';
CREATE INDEX idx_revision_source ON operation_revision(source_evidence_id, source_row_no);
ALTER TABLE operation_revision ADD CONSTRAINT fk_revision_source_evidence
    FOREIGN KEY (source_evidence_id) REFERENCES source_evidence(id);
ALTER TABLE operation_import_batch ADD COLUMN source_evidence_id BIGINT NULL;
ALTER TABLE operation_import_batch ADD CONSTRAINT fk_import_batch_source_evidence
    FOREIGN KEY (source_evidence_id) REFERENCES source_evidence(id);
