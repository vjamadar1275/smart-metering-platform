-- reference.dim_customer — customer account master data.
--
-- See dim_dma.sql for why this is a directly-runnable seed script rather
-- than pipeline-generated DDL, and for the SCD Type 2 rationale.
--
-- Seed data is synthetic (no real customer PII) — representative account
-- mix across customer types and the DMAs defined in dim_dma.sql.

CREATE TABLE IF NOT EXISTS reference.dim_customer (
    customer_sk           BIGINT      COMMENT 'Surrogate key, stable across SCD2 revisions of the same customer_id.',
    customer_id            STRING      COMMENT 'Natural key: customer account identifier.',
    account_number          STRING      COMMENT 'Billing account number, as shown on customer invoices.',
    customer_type            STRING      COMMENT 'RESIDENTIAL | COMMERCIAL | INDUSTRIAL | MUNICIPAL.',
    service_dma_id            STRING      COMMENT 'FK to reference.dim_dma.dma_id — the DMA serving this account.',
    account_status            STRING      COMMENT 'ACTIVE | INACTIVE | CLOSED.',
    billing_cycle             STRING      COMMENT 'MONTHLY | QUARTERLY — drives gold.customer_analytics aggregation windows.',
    effective_start_date      DATE        COMMENT 'SCD2: date this customer revision took effect.',
    effective_end_date        DATE        COMMENT 'SCD2: date this customer revision was superseded; NULL if current.',
    is_current                 BOOLEAN     COMMENT 'SCD2: true for the currently-active revision of this customer_id.'
)
USING DELTA
COMMENT 'Reference (dimension) table: customer account master data, SCD Type 2. Synthetic seed data — no real customer PII.'
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'quality' = 'reference'
);

INSERT OVERWRITE reference.dim_customer
VALUES
    (1,  'CUST-0001', 'ACC-100001', 'RESIDENTIAL', 'DMA-001', 'ACTIVE', 'MONTHLY',   DATE'2021-03-01', NULL, true),
    (2,  'CUST-0002', 'ACC-100002', 'RESIDENTIAL', 'DMA-001', 'ACTIVE', 'MONTHLY',   DATE'2021-03-01', NULL, true),
    (3,  'CUST-0003', 'ACC-100003', 'RESIDENTIAL', 'DMA-002', 'ACTIVE', 'MONTHLY',   DATE'2021-04-15', NULL, true),
    (4,  'CUST-0004', 'ACC-100004', 'RESIDENTIAL', 'DMA-002', 'ACTIVE', 'MONTHLY',   DATE'2021-04-15', NULL, true),
    (5,  'CUST-0005', 'ACC-100005', 'COMMERCIAL',  'DMA-003', 'ACTIVE', 'MONTHLY',   DATE'2020-11-01', NULL, true),
    (6,  'CUST-0006', 'ACC-100006', 'COMMERCIAL',  'DMA-003', 'ACTIVE', 'MONTHLY',   DATE'2020-11-01', NULL, true),
    (7,  'CUST-0007', 'ACC-100007', 'RESIDENTIAL', 'DMA-004', 'ACTIVE', 'MONTHLY',   DATE'2022-01-10', NULL, true),
    (8,  'CUST-0008', 'ACC-100008', 'RESIDENTIAL', 'DMA-004', 'INACTIVE', 'MONTHLY', DATE'2022-01-10', NULL, true),
    (9,  'CUST-0009', 'ACC-100009', 'RESIDENTIAL', 'DMA-005', 'ACTIVE', 'MONTHLY',   DATE'2021-07-22', NULL, true),
    (10, 'CUST-0010', 'ACC-100010', 'RESIDENTIAL', 'DMA-005', 'ACTIVE', 'MONTHLY',   DATE'2021-07-22', NULL, true),
    (11, 'CUST-0011', 'ACC-100011', 'INDUSTRIAL',  'DMA-006', 'ACTIVE', 'MONTHLY',   DATE'2020-06-01', NULL, true),
    (12, 'CUST-0012', 'ACC-100012', 'INDUSTRIAL',  'DMA-006', 'ACTIVE', 'MONTHLY',   DATE'2020-06-01', NULL, true),
    (13, 'CUST-0013', 'ACC-100013', 'RESIDENTIAL', 'DMA-007', 'ACTIVE', 'MONTHLY',   DATE'2021-09-05', NULL, true),
    (14, 'CUST-0014', 'ACC-100014', 'RESIDENTIAL', 'DMA-007', 'ACTIVE', 'MONTHLY',   DATE'2021-09-05', NULL, true),
    (15, 'CUST-0015', 'ACC-100015', 'RESIDENTIAL', 'DMA-007', 'ACTIVE', 'MONTHLY',   DATE'2021-09-05', NULL, true),
    (16, 'CUST-0016', 'ACC-100016', 'RESIDENTIAL', 'DMA-008', 'ACTIVE', 'MONTHLY',   DATE'2022-02-14', NULL, true),
    (17, 'CUST-0017', 'ACC-100017', 'RESIDENTIAL', 'DMA-008', 'ACTIVE', 'MONTHLY',   DATE'2022-02-14', NULL, true),
    (18, 'CUST-0018', 'ACC-100018', 'MUNICIPAL',   'DMA-001', 'ACTIVE', 'QUARTERLY', DATE'2020-01-15', NULL, true),
    (19, 'CUST-0019', 'ACC-100019', 'COMMERCIAL',  'DMA-002', 'ACTIVE', 'MONTHLY',   DATE'2021-05-20', NULL, true),
    (20, 'CUST-0020', 'ACC-100020', 'RESIDENTIAL', 'DMA-003', 'ACTIVE', 'MONTHLY',   DATE'2021-08-11', NULL, true),
    (21, 'CUST-0021', 'ACC-100021', 'RESIDENTIAL', 'DMA-004', 'ACTIVE', 'MONTHLY',   DATE'2022-03-01', NULL, true),
    (22, 'CUST-0022', 'ACC-100022', 'RESIDENTIAL', 'DMA-005', 'CLOSED',  'MONTHLY',  DATE'2020-09-01', NULL, true),
    (23, 'CUST-0023', 'ACC-100023', 'COMMERCIAL',  'DMA-006', 'ACTIVE', 'MONTHLY',   DATE'2021-11-30', NULL, true),
    (24, 'CUST-0024', 'ACC-100024', 'RESIDENTIAL', 'DMA-007', 'ACTIVE', 'MONTHLY',   DATE'2022-04-18', NULL, true),
    (25, 'CUST-0025', 'ACC-100025', 'RESIDENTIAL', 'DMA-008', 'ACTIVE', 'MONTHLY',   DATE'2022-05-02', NULL, true),
    (26, 'CUST-0026', 'ACC-100026', 'RESIDENTIAL', 'DMA-001', 'ACTIVE', 'MONTHLY',   DATE'2022-06-19', NULL, true),
    (27, 'CUST-0027', 'ACC-100027', 'RESIDENTIAL', 'DMA-002', 'ACTIVE', 'MONTHLY',   DATE'2022-07-07', NULL, true),
    (28, 'CUST-0028', 'ACC-100028', 'INDUSTRIAL',  'DMA-003', 'ACTIVE', 'MONTHLY',   DATE'2020-12-12', NULL, true),
    (29, 'CUST-0029', 'ACC-100029', 'RESIDENTIAL', 'DMA-004', 'ACTIVE', 'MONTHLY',   DATE'2022-08-25', NULL, true),
    (30, 'CUST-0030', 'ACC-100030', 'RESIDENTIAL', 'DMA-005', 'ACTIVE', 'MONTHLY',   DATE'2022-09-09', NULL, true);
