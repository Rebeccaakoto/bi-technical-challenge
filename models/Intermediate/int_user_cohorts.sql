-- One row per user with their cohort.
-- Cohort = month of the user's first product-usage event (not account creation).

WITH first_activity AS (

    SELECT
        USER_ID,
        MIN(ACTIVITY_MONTH) AS COHORT_MONTH
    FROM {{ ref('int_user_activity') }}
    GROUP BY USER_ID

)

SELECT
    USER_ID,
    COHORT_MONTH
FROM first_activity