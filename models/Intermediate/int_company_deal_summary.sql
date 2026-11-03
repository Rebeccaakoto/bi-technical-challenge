
WITH company_deals AS (

    SELECT
        HUBSPOT_COMPANY_ID,

        COUNT(DISTINCT DEAL_ID) AS TOTAL_DEALS,

        COUNT_IF(DEAL_STATUS = 'won') AS WON_DEALS,

        COUNT_IF(DEAL_STATUS = 'lost') AS LOST_DEALS,

        COUNT_IF(DEAL_STATUS = 'open') AS OPEN_DEALS,

        COUNT_IF(
            ENTERED_CLOSED_WON_AT IS NOT NULL
        ) AS DEALS_EVER_WON,

        COUNT_IF(
            ENTERED_CLOSED_WON_AT IS NOT NULL
            AND ENTERED_CLOSED_LOST_AT >
                ENTERED_CLOSED_WON_AT
        ) AS WON_THEN_LOST_DEALS,

        COUNT_IF(
            DEAL_STATUS = 'open'
            AND LOWER(DEAL_TYPE) = 'newbusiness'
        ) AS OPEN_NEW_BUSINESS_DEALS,

        COUNT_IF(
            DEAL_STATUS = 'open'
            AND LOWER(DEAL_TYPE) = 'existing_business'
        ) AS OPEN_EXPANSION_DEALS

    FROM {{ ref('stg_hubspot_deals') }}

    GROUP BY HUBSPOT_COMPANY_ID

)

SELECT *
FROM company_deals
