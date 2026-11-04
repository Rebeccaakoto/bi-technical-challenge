WITH organization_created AS (
    SELECT
        ORGANIZATION_ID,
        MIN(EVENT_AT) AS CREATED_AT
    FROM {{ ref('stg_backend_events') }}
    WHERE EVENT_NAME = 'OrganizationCreated'
      AND ORGANIZATION_ID IS NOT NULL
    GROUP BY ORGANIZATION_ID
),

first_search AS (
    SELECT
        e.ORGANIZATION_ID,
        MIN(e.EVENT_AT) AS FIRST_SEARCH_AT
    FROM {{ ref('stg_backend_events') }} e
    INNER JOIN organization_created o
        ON e.ORGANIZATION_ID = o.ORGANIZATION_ID
    WHERE e.EVENT_NAME = 'SearchExecuted'
      AND e.EVENT_AT >= o.CREATED_AT
    GROUP BY e.ORGANIZATION_ID
),

data_cutoff AS (
    SELECT MAX(EVENT_AT) AS DATA_END_DATE
    FROM {{ ref('stg_backend_events') }}
),

organization_ttfv AS (
    SELECT
        o.ORGANIZATION_ID,
        o.CREATED_AT,
        f.FIRST_SEARCH_AT,
        d.DATA_END_DATE,

        DATEDIFF(
            'SECOND',
            o.CREATED_AT,
            f.FIRST_SEARCH_AT
        ) / 3600.0 AS TTFV_HOURS,

        f.FIRST_SEARCH_AT IS NOT NULL AS IS_ACTIVATED,

        o.CREATED_AT <= DATEADD(DAY, -7, d.DATA_END_DATE)
            AS ELIGIBLE_FOR_7_DAY_MEASUREMENT,

        o.CREATED_AT <= DATEADD(DAY, -30, d.DATA_END_DATE)
            AS ELIGIBLE_FOR_30_DAY_MEASUREMENT

    FROM organization_created o
    CROSS JOIN data_cutoff d
    LEFT JOIN first_search f
        ON o.ORGANIZATION_ID = f.ORGANIZATION_ID
)

SELECT
    ORGANIZATION_ID,
    CREATED_AT,
    FIRST_SEARCH_AT,
    DATA_END_DATE,
    ROUND(TTFV_HOURS, 2) AS TTFV_HOURS,
    ROUND(TTFV_HOURS / 24.0, 2) AS TTFV_DAYS,
    IS_ACTIVATED,
    ELIGIBLE_FOR_7_DAY_MEASUREMENT,
    ELIGIBLE_FOR_30_DAY_MEASUREMENT,

    CASE
        WHEN NOT ELIGIBLE_FOR_7_DAY_MEASUREMENT THEN NULL
        WHEN TTFV_HOURS <= 168 THEN TRUE
        ELSE FALSE
    END AS ACTIVATED_WITHIN_7_DAYS,

    CASE
        WHEN NOT ELIGIBLE_FOR_30_DAY_MEASUREMENT THEN NULL
        WHEN TTFV_HOURS <= 720 THEN TRUE
        ELSE FALSE
    END AS ACTIVATED_WITHIN_30_DAYS

FROM organization_ttfv