# Performance Tests

Regression guards for the Gold/ML transform functions at a larger synthetic scale (tens of thousands of rows) than [tests/unit/](../unit/)'s small, exact-value fixtures — run entirely on local PySpark, no live Databricks workspace needed, always run (never skipped) since they don't depend on external credentials.

**What these are not**: real cluster-scale benchmarks. They exist to catch an algorithmic regression (an accidental row-by-row UDF, a join that turns into a cross join) locally/in CI, not to validate this platform's actual production sizing — see [docs/guides/PERFORMANCE_GUIDE.md](../../docs/guides/PERFORMANCE_GUIDE.md) for the real sizing methodology, which needs a live cluster and production-representative data this sandbox doesn't have.

Thresholds (`MAX_SECONDS` in [test_transform_benchmarks.py](test_transform_benchmarks.py)) are deliberately generous — treat a failure as "something got algorithmically much worse," not "this is exactly how fast it should be."
