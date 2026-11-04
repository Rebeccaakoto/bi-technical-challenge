-- Bonus insight: at which stage are new-business deals lost?
-- Furthest stage = the last stage a lost deal entered before it was closed lost.
-- Put this in analyses/.

WITH lost_deals AS (

    SELECT
        DEAL_ID,
        CASE
            WHEN ENTERED_CONTRACT_NEGOTIATION_AT IS NOT NULL THEN '5_contract_negotiation'
            WHEN ENTERED_PRICE_OFFERING_AT       IS NOT NULL THEN '4_price_offering'
            WHEN ENTERED_PRODUCT_TESTING_AT      IS NOT NULL THEN '3_product_testing'
            WHEN ENTERED_PITCHING_AT             IS NOT NULL THEN '2_pitching'
            ELSE '1_pre_pitch'
        END AS FURTHEST_STAGE
    FROM {{ ref('stg_hubspot_deals') }}
    WHERE DEAL_TYPE = 'newbusiness'
      AND DEAL_STATUS = 'lost'

)

SELECT
    FURTHEST_STAGE,
    COUNT(*)                                                    AS LOST_DEALS,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)          AS PCT_OF_LOST
FROM lost_deals
GROUP BY FURTHEST_STAGE
ORDER BY FURTHEST_STAGE