-- One row per user per active month, enriched with the user's cohort and the
-- number of months since the cohort month (0 = the cohort month itself).

WITH user_activity AS (

    SELECT *
    FROM {{ ref('int_user_activity') }}

),

user_cohorts AS (

    SELECT *
    FROM {{ ref('int_user_cohorts') }}

),

cohort_activity AS (

    SELECT
        a.USER_ID,
        a.USER_MONTH_KEY,
        c.COHORT_MONTH,
        a.ACTIVITY_MONTH,
        DATEDIFF('MONTH', c.COHORT_MONTH, a.ACTIVITY_MONTH) AS MONTHS_SINCE_COHORT,
        a.PRODUCT_EVENTS,
        a.DISTINCT_EVENT_TYPES,
        a.FIRST_ACTIVITY_AT,
        a.LAST_ACTIVITY_AT
    FROM user_activity a
    INNER JOIN user_cohorts c
        ON a.USER_ID = c.USER_ID

)

SELECT *
FROM cohort_activity