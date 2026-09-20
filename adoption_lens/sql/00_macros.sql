CREATE OR REPLACE MACRO wilson_lo(x, n) AS
    (x + 1.96 * 1.96 / 2.0 - 1.96 * sqrt(x * (n - x) / n + 1.96 * 1.96 / 4.0)) / (n + 1.96 * 1.96);

CREATE OR REPLACE MACRO wilson_hi(x, n) AS
    (x + 1.96 * 1.96 / 2.0 + 1.96 * sqrt(x * (n - x) / n + 1.96 * 1.96 / 4.0)) / (n + 1.96 * 1.96);
