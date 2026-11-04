WITH companies AS (

    SELECT
       COMPANY_ID as  HUBSPOT_COMPANY_ID,
        COMPANY_NAME,
        DOMAIN,
        INDUSTRY,
        COUNTRY,
       CREATED_AT::date as  CREATE_DATE
    FROM {{ ref('stg_hubspot_companies') }}

),

deal_summary AS (

    SELECT *
    FROM {{ ref('int_company_deal_summary') }}

),

customer_portfolio AS (

    SELECT
        c.HUBSPOT_COMPANY_ID,
        c.COMPANY_NAME,
        c.DOMAIN,
        c.INDUSTRY,
        c.COUNTRY,
        c.CREATE_DATE,

        COALESCE(d.TOTAL_DEALS, 0) AS TOTAL_DEALS,
        COALESCE(d.WON_DEALS, 0) AS WON_DEALS,
        COALESCE(d.LOST_DEALS, 0) AS LOST_DEALS,
        COALESCE(d.OPEN_DEALS, 0) AS OPEN_DEALS,
        COALESCE(d.DEALS_EVER_WON, 0) AS DEALS_EVER_WON,
        COALESCE(d.WON_THEN_LOST_DEALS, 0)
            AS WON_THEN_LOST_DEALS,
        COALESCE(d.OPEN_NEW_BUSINESS_DEALS, 0)
            AS OPEN_NEW_BUSINESS_DEALS,
        COALESCE(d.OPEN_EXPANSION_DEALS, 0)
            AS OPEN_EXPANSION_DEALS,

        CASE
            WHEN COALESCE(d.WON_DEALS, 0) > 0
                THEN 'Active Customer'

            WHEN COALESCE(d.WON_THEN_LOST_DEALS, 0) > 0
                THEN 'Passive Churned'

            WHEN COALESCE(d.DEALS_EVER_WON, 0) = 0
                 AND COALESCE(d.LOST_DEALS, 0) > 0
                THEN 'Churned-Lost'

            WHEN COALESCE(d.DEALS_EVER_WON, 0) = 0
                 AND COALESCE(d.OPEN_NEW_BUSINESS_DEALS, 0) > 0
                THEN 'Open New Business'

            WHEN COALESCE(d.TOTAL_DEALS, 0) = 0
                THEN 'Lead'

            ELSE 'Needs Review'
        END AS CUSTOMER_STATUS

    FROM companies c

    LEFT JOIN deal_summary d
        ON c.HUBSPOT_COMPANY_ID = d.HUBSPOT_COMPANY_ID

)

SELECT *
FROM customer_portfolio