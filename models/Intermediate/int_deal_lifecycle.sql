WITH deals AS (

    SELECT *
    FROM {{ ref('stg_hubspot_deals') }}

),

deal_lifecycle AS (

    SELECT
        DEAL_ID,
        DEAL_NAME,
        HUBSPOT_COMPANY_ID,
        PIPELINE,
        DEAL_TYPE,

        AMOUNT,
        CURRENCY,

        DEAL_STATUS,
        IS_CLOSED,
        IS_CLOSED_WON,

        CREATED_AT,
        CLOSED_AT,

        ENTERED_PRE_PITCH_AT,
        ENTERED_PITCHING_AT,
        ENTERED_PRODUCT_TESTING_AT,
        ENTERED_PRICE_OFFERING_AT,
        ENTERED_CONTRACT_NEGOTIATION_AT,
        ENTERED_CLOSED_WON_AT,
        ENTERED_CLOSED_LOST_AT,

        DATEDIFF(
            'day',
            CREATED_AT,
            CLOSED_AT
        ) AS SALES_CYCLE_DAYS,

        CASE
            WHEN DEAL_STATUS = 'won' THEN 1
            ELSE 0
        END AS IS_WON,

        CASE
            WHEN DEAL_STATUS = 'lost' THEN 1
            ELSE 0
        END AS IS_LOST,

        CASE
            WHEN DEAL_STATUS = 'open' THEN 1
            ELSE 0
        END AS IS_OPEN

    FROM deals

)

SELECT *
FROM deal_lifecycle