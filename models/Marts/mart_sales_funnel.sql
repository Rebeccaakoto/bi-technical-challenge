
WITH deal_stages AS (

    SELECT
        DEAL_ID,
        DEAL_STATUS,

        COALESCE(
            ENTERED_PITCHING_AT,
            ENTERED_PRODUCT_TESTING_AT,
            ENTERED_PRICE_OFFERING_AT,
            ENTERED_CONTRACT_NEGOTIATION_AT,
            ENTERED_CLOSED_WON_AT
        ) IS NOT NULL AS REACHED_PITCHING,

        COALESCE(
            ENTERED_PRODUCT_TESTING_AT,
            ENTERED_PRICE_OFFERING_AT,
            ENTERED_CONTRACT_NEGOTIATION_AT,
            ENTERED_CLOSED_WON_AT
        ) IS NOT NULL AS REACHED_PRODUCT_TESTING,

        COALESCE(
            ENTERED_PRICE_OFFERING_AT,
            ENTERED_CONTRACT_NEGOTIATION_AT,
            ENTERED_CLOSED_WON_AT
        ) IS NOT NULL AS REACHED_PRICE_OFFERING,

        COALESCE(
            ENTERED_CONTRACT_NEGOTIATION_AT,
            ENTERED_CLOSED_WON_AT
        ) IS NOT NULL AS REACHED_CONTRACT_NEGOTIATION,

        LOWER(DEAL_STATUS) = 'won' AS REACHED_WON

    FROM {{ ref('stg_hubspot_deals') }}
    WHERE LOWER(DEAL_TYPE) = 'newbusiness'

),

stage_counts AS (

    SELECT
        1 AS STEP_ORDER,
        'New-business Deals Created' AS STAGE,
        COUNT(DISTINCT DEAL_ID) AS DEALS
    FROM deal_stages

    UNION ALL

    SELECT
        2, 'Pitching',
        COUNT(DISTINCT CASE WHEN REACHED_PITCHING THEN DEAL_ID END)
    FROM deal_stages

    UNION ALL

    SELECT
        3, 'Product Testing',
        COUNT(DISTINCT CASE WHEN REACHED_PRODUCT_TESTING THEN DEAL_ID END)
    FROM deal_stages

    UNION ALL

    SELECT
        4, 'Price Offering',
        COUNT(DISTINCT CASE WHEN REACHED_PRICE_OFFERING THEN DEAL_ID END)
    FROM deal_stages

    UNION ALL

    SELECT
        5, 'Contract Negotiation',
        COUNT(DISTINCT CASE WHEN REACHED_CONTRACT_NEGOTIATION THEN DEAL_ID END)
    FROM deal_stages

    UNION ALL

    SELECT
        6, 'Won',
        COUNT(DISTINCT CASE WHEN REACHED_WON THEN DEAL_ID END)
    FROM deal_stages

),

funnel_with_previous AS (

    SELECT
        STEP_ORDER,
        STAGE,
        DEALS,

        LAG(DEALS) OVER (
            ORDER BY STEP_ORDER
        ) AS PREVIOUS_STAGE_DEALS,

        FIRST_VALUE(DEALS) OVER (
            ORDER BY STEP_ORDER
            ROWS BETWEEN UNBOUNDED PRECEDING
            AND UNBOUNDED FOLLOWING
        ) AS TOTAL_DEALS

    FROM stage_counts

)

SELECT
    STEP_ORDER,
    STAGE,
    DEALS,

    ROUND(
        100.0 * DEALS
        / NULLIF(PREVIOUS_STAGE_DEALS, 0),
        2
    ) AS CONVERSION_FROM_PREVIOUS_STAGE,

    ROUND(
        100.0 * DEALS
        / NULLIF(TOTAL_DEALS, 0),
        2
    ) AS CONVERSION_FROM_DEAL_CREATED

FROM funnel_with_previous
ORDER BY STEP_ORDER

