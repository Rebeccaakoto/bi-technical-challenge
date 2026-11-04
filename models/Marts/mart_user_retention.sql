-- Q3: What is the retention of our users?
--
-- Monthly cohort retention. One row per cohort month x months since cohort.
--   COHORT_MONTH         = month of a user's first product-usage event
--   MONTHS_SINCE_COHORT  = 0, 1, 2, ... months after the cohort month
--   ACTIVE_USERS         = users of the cohort with product usage in that month
--   RETENTION_RATE       = ACTIVE_USERS / COHORT_SIZE * 100
--
-- Every cohort x month combination up to the last COMPLETE month is generated,
-- so months with zero active users show 0% instead of being missing.
-- The last, partial month in the data (Feb 2026, 8 days) is excluded.

WITH cohort_sizes AS (

    SELECT
        COHORT_MONTH,
        COUNT(DISTINCT USER_ID) AS COHORT_SIZE
    FROM {{ ref('int_user_cohorts') }}
    GROUP BY COHORT_MONTH

),

monthly_cohort_activity AS (

    SELECT
        COHORT_MONTH,
        MONTHS_SINCE_COHORT,
        COUNT(DISTINCT USER_ID) AS ACTIVE_USERS
    FROM {{ ref('int_user_cohort_activity') }}
    GROUP BY
        COHORT_MONTH,
        MONTHS_SINCE_COHORT

),

last_complete_month AS (

    -- the month before the last month in the data, because that one is partial
    SELECT
        DATEADD('MONTH', -1, DATE_TRUNC('MONTH', MAX(EVENT_DATE)))::DATE AS LAST_COMPLETE_MONTH
    FROM {{ ref('stg_backend_events') }}

),

month_offsets AS (

    -- gap-free 0, 1, 2, ... (SEQ4() alone is not guaranteed to be gap-free)
    -- 100 is an upper bound; the data spans 20 months
    SELECT ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1 AS MONTHS_SINCE_COHORT
    FROM TABLE(GENERATOR(ROWCOUNT => 100))

),

cohort_calendar AS (

    -- every month each cohort could have been observed
    SELECT
        c.COHORT_MONTH,
        c.COHORT_SIZE,
        m.MONTHS_SINCE_COHORT,
        DATEADD('MONTH', m.MONTHS_SINCE_COHORT, c.COHORT_MONTH)::DATE AS ACTIVITY_MONTH
    FROM cohort_sizes c
    CROSS JOIN month_offsets m
    CROSS JOIN last_complete_month l
    WHERE DATEADD('MONTH', m.MONTHS_SINCE_COHORT, c.COHORT_MONTH) <= l.LAST_COMPLETE_MONTH

),

retention AS (

    SELECT
        c.COHORT_MONTH,
        c.ACTIVITY_MONTH,
        c.MONTHS_SINCE_COHORT,
        TO_VARCHAR(c.COHORT_MONTH) || '-' || c.MONTHS_SINCE_COHORT     AS COHORT_MONTH_KEY,  
        c.COHORT_SIZE,
        COALESCE(a.ACTIVE_USERS, 0)                                     AS ACTIVE_USERS,
        ROUND(100.0 * COALESCE(a.ACTIVE_USERS, 0) / NULLIF(c.COHORT_SIZE, 0), 2) AS RETENTION_RATE
    FROM cohort_calendar c
    LEFT JOIN monthly_cohort_activity a
        ON  c.COHORT_MONTH = a.COHORT_MONTH
        AND c.MONTHS_SINCE_COHORT = a.MONTHS_SINCE_COHORT

)

SELECT *
FROM retention