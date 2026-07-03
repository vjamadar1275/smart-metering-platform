-- reference.dim_meter — smart meter asset master data.
--
-- See dim_dma.sql for why this is a directly-runnable seed script and for
-- the SCD Type 2 rationale. Silver's referential-integrity expectation
-- (docs/architecture/ARCHITECTURE.md#3-bronze--silver) checks incoming
-- telemetry.meter_id against this table's *current* rows; a meter_id with
-- no current row here is quarantined with reason "unknown_meter_id" rather
-- than silently enriched with nulls.
--
-- Seed data: one meter per seeded customer in dim_customer.sql (1:1
-- service-connection assumption for this representative sample), matching
-- each customer's service_dma_id.

CREATE TABLE IF NOT EXISTS reference.dim_meter (
    meter_sk               BIGINT      COMMENT 'Surrogate key, stable across SCD2 revisions of the same meter_id.',
    meter_id                STRING      COMMENT 'Natural key: unique smart meter identifier, matches telemetry.meter_id.',
    customer_id              STRING      COMMENT 'FK to reference.dim_customer.customer_id — the account this meter bills to.',
    dma_id                    STRING      COMMENT 'FK to reference.dim_dma.dma_id — the DMA this meter belongs to.',
    meter_type                STRING      COMMENT 'ULTRASONIC | MECHANICAL | AMR.',
    meter_size_mm              INT         COMMENT 'Nominal meter bore size, millimeters.',
    expected_unit               STRING      COMMENT 'LITERS | GALLONS | CUBIC_METERS — the unit this meter''s firmware is configured to report; a telemetry event reporting a different unit is a Silver expectation failure (reason "unit_mismatch").',
    install_date                 DATE        COMMENT 'Date the meter was physically installed; readings dated before this are implausible (reason "reading_before_install").',
    status                        STRING      COMMENT 'ACTIVE | DECOMMISSIONED.',
    effective_start_date          DATE        COMMENT 'SCD2: date this meter revision took effect.',
    effective_end_date             DATE        COMMENT 'SCD2: date this meter revision was superseded; NULL if current.',
    is_current                      BOOLEAN     COMMENT 'SCD2: true for the currently-active revision of this meter_id.'
)
USING DELTA
COMMENT 'Reference (dimension) table: smart meter asset master data, SCD Type 2. Synthetic seed data, 1:1 with reference.dim_customer for this representative sample.'
TBLPROPERTIES (
    'delta.enableChangeDataFeed' = 'true',
    'quality' = 'reference'
);

INSERT OVERWRITE reference.dim_meter
VALUES
    (1,  'MTR-000001', 'CUST-0001', 'DMA-001', 'ULTRASONIC', 20, 'LITERS', DATE'2021-03-01', 'ACTIVE', DATE'2021-03-01', NULL, true),
    (2,  'MTR-000002', 'CUST-0002', 'DMA-001', 'ULTRASONIC', 20, 'LITERS', DATE'2021-03-01', 'ACTIVE', DATE'2021-03-01', NULL, true),
    (3,  'MTR-000003', 'CUST-0003', 'DMA-002', 'MECHANICAL', 15, 'LITERS', DATE'2021-04-15', 'ACTIVE', DATE'2021-04-15', NULL, true),
    (4,  'MTR-000004', 'CUST-0004', 'DMA-002', 'MECHANICAL', 15, 'LITERS', DATE'2021-04-15', 'ACTIVE', DATE'2021-04-15', NULL, true),
    (5,  'MTR-000005', 'CUST-0005', 'DMA-003', 'AMR',        40, 'CUBIC_METERS', DATE'2020-11-01', 'ACTIVE', DATE'2020-11-01', NULL, true),
    (6,  'MTR-000006', 'CUST-0006', 'DMA-003', 'AMR',        40, 'CUBIC_METERS', DATE'2020-11-01', 'ACTIVE', DATE'2020-11-01', NULL, true),
    (7,  'MTR-000007', 'CUST-0007', 'DMA-004', 'ULTRASONIC', 20, 'LITERS', DATE'2022-01-10', 'ACTIVE', DATE'2022-01-10', NULL, true),
    (8,  'MTR-000008', 'CUST-0008', 'DMA-004', 'ULTRASONIC', 20, 'LITERS', DATE'2022-01-10', 'DECOMMISSIONED', DATE'2022-01-10', NULL, true),
    (9,  'MTR-000009', 'CUST-0009', 'DMA-005', 'MECHANICAL', 15, 'LITERS', DATE'2021-07-22', 'ACTIVE', DATE'2021-07-22', NULL, true),
    (10, 'MTR-000010', 'CUST-0010', 'DMA-005', 'MECHANICAL', 15, 'LITERS', DATE'2021-07-22', 'ACTIVE', DATE'2021-07-22', NULL, true),
    (11, 'MTR-000011', 'CUST-0011', 'DMA-006', 'AMR',        80, 'CUBIC_METERS', DATE'2020-06-01', 'ACTIVE', DATE'2020-06-01', NULL, true),
    (12, 'MTR-000012', 'CUST-0012', 'DMA-006', 'AMR',        80, 'CUBIC_METERS', DATE'2020-06-01', 'ACTIVE', DATE'2020-06-01', NULL, true),
    (13, 'MTR-000013', 'CUST-0013', 'DMA-007', 'ULTRASONIC', 20, 'GALLONS', DATE'2021-09-05', 'ACTIVE', DATE'2021-09-05', NULL, true),
    (14, 'MTR-000014', 'CUST-0014', 'DMA-007', 'ULTRASONIC', 20, 'GALLONS', DATE'2021-09-05', 'ACTIVE', DATE'2021-09-05', NULL, true),
    (15, 'MTR-000015', 'CUST-0015', 'DMA-007', 'ULTRASONIC', 20, 'GALLONS', DATE'2021-09-05', 'ACTIVE', DATE'2021-09-05', NULL, true),
    (16, 'MTR-000016', 'CUST-0016', 'DMA-008', 'MECHANICAL', 15, 'LITERS', DATE'2022-02-14', 'ACTIVE', DATE'2022-02-14', NULL, true),
    (17, 'MTR-000017', 'CUST-0017', 'DMA-008', 'MECHANICAL', 15, 'LITERS', DATE'2022-02-14', 'ACTIVE', DATE'2022-02-14', NULL, true),
    (18, 'MTR-000018', 'CUST-0018', 'DMA-001', 'AMR',        100, 'CUBIC_METERS', DATE'2020-01-15', 'ACTIVE', DATE'2020-01-15', NULL, true),
    (19, 'MTR-000019', 'CUST-0019', 'DMA-002', 'AMR',        50, 'CUBIC_METERS', DATE'2021-05-20', 'ACTIVE', DATE'2021-05-20', NULL, true),
    (20, 'MTR-000020', 'CUST-0020', 'DMA-003', 'ULTRASONIC', 20, 'LITERS', DATE'2021-08-11', 'ACTIVE', DATE'2021-08-11', NULL, true),
    (21, 'MTR-000021', 'CUST-0021', 'DMA-004', 'ULTRASONIC', 20, 'LITERS', DATE'2022-03-01', 'ACTIVE', DATE'2022-03-01', NULL, true),
    (22, 'MTR-000022', 'CUST-0022', 'DMA-005', 'MECHANICAL', 15, 'LITERS', DATE'2020-09-01', 'DECOMMISSIONED', DATE'2020-09-01', NULL, true),
    (23, 'MTR-000023', 'CUST-0023', 'DMA-006', 'AMR',        50, 'CUBIC_METERS', DATE'2021-11-30', 'ACTIVE', DATE'2021-11-30', NULL, true),
    (24, 'MTR-000024', 'CUST-0024', 'DMA-007', 'ULTRASONIC', 20, 'GALLONS', DATE'2022-04-18', 'ACTIVE', DATE'2022-04-18', NULL, true),
    (25, 'MTR-000025', 'CUST-0025', 'DMA-008', 'MECHANICAL', 15, 'LITERS', DATE'2022-05-02', 'ACTIVE', DATE'2022-05-02', NULL, true),
    (26, 'MTR-000026', 'CUST-0026', 'DMA-001', 'ULTRASONIC', 20, 'LITERS', DATE'2022-06-19', 'ACTIVE', DATE'2022-06-19', NULL, true),
    (27, 'MTR-000027', 'CUST-0027', 'DMA-002', 'ULTRASONIC', 20, 'LITERS', DATE'2022-07-07', 'ACTIVE', DATE'2022-07-07', NULL, true),
    (28, 'MTR-000028', 'CUST-0028', 'DMA-003', 'AMR',        60, 'CUBIC_METERS', DATE'2020-12-12', 'ACTIVE', DATE'2020-12-12', NULL, true),
    (29, 'MTR-000029', 'CUST-0029', 'DMA-004', 'ULTRASONIC', 20, 'LITERS', DATE'2022-08-25', 'ACTIVE', DATE'2022-08-25', NULL, true),
    (30, 'MTR-000030', 'CUST-0030', 'DMA-005', 'MECHANICAL', 15, 'LITERS', DATE'2022-09-09', 'ACTIVE', DATE'2022-09-09', NULL, true);
