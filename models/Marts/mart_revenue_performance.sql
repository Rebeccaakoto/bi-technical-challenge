WITH won_deals AS (

    SELECT
        DEAL_ID,
        HUBSPOT_COMPANY_ID,
        DEAL_TYPE,
        AMOUNT,
        CURRENCY,
        CLOSED_AT
    FROM {{ ref('int_deal_lifecycle') }}
    WHERE DEAL_STATUS = 'won'

),

revenue_by_deal_type AS (

    SELECT
        DEAL_TYPE,
        CURRENCY,

        COUNT(DISTINCT DEAL_ID) AS WON_DEALS,

        SUM(AMOUNT) AS TOTAL_WON_VALUE,

        AVG(AMOUNT) AS AVERAGE_DEAL_VALUE,

        MIN(AMOUNT) AS MIN_DEAL_VALUE,

        MAX(AMOUNT) AS MAX_DEAL_VALUE

    FROM won_deals

    GROUP BY
        DEAL_TYPE,
        CURRENCY

)

SELECT
    DEAL_TYPE,
    CURRENCY,
    WON_DEALS,
    TOTAL_WON_VALUE,
    AVERAGE_DEAL_VALUE,
    MIN_DEAL_VALUE,
    MAX_DEAL_VALUE
FROM revenue_by_deal_type