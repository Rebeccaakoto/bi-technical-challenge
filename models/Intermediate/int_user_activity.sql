-- One row per user per month in which the user was ACTIVE.
-- Active = at least one product-usage event (IS_PRODUCT_USAGE = TRUE), which
-- excludes TokenGenerated (login / session refresh) and account admin events.
-- Months without activity do not appear here; mart_user_retention fills them in.

WITH product_events AS (

    SELECT
        USER_ID,
        ORGANIZATION_ID,
        EVENT_ID,
        EVENT_NAME,
        EVENT_AT,
        DATE_TRUNC('MONTH', EVENT_AT)::DATE AS ACTIVITY_MONTH
    FROM {{ ref('stg_backend_events') }}
    WHERE IS_PRODUCT_USAGE = TRUE
      AND USER_ID IS NOT NULL

),

monthly_activity AS (

    SELECT
        USER_ID,
        ACTIVITY_MONTH,
        USER_ID || '-' || TO_VARCHAR(ACTIVITY_MONTH)   AS USER_MONTH_KEY,   -- grain key, tested unique
        ANY_VALUE(ORGANIZATION_ID)                     AS ORGANIZATION_ID,
        COUNT(DISTINCT EVENT_ID)                       AS PRODUCT_EVENTS,
        COUNT(DISTINCT EVENT_NAME)                     AS DISTINCT_EVENT_TYPES,
        MIN(EVENT_AT)                                  AS FIRST_ACTIVITY_AT,
        MAX(EVENT_AT)                                  AS LAST_ACTIVITY_AT
    FROM product_events
    GROUP BY
        USER_ID,
        ACTIVITY_MONTH

)

SELECT *
FROM monthly_activity