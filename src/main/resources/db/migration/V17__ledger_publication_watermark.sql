CREATE TABLE ledger_publication_state (
    id INT PRIMARY KEY,
    sequence_value BIGINT NOT NULL
);
INSERT INTO ledger_publication_state(id, sequence_value) VALUES (1, 0);
ALTER TABLE operation_revision ADD COLUMN publication_seq BIGINT NOT NULL DEFAULT 0;
CREATE INDEX idx_revision_publication ON operation_revision(operation_id, publication_seq, id);
