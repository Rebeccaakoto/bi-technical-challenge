
-- One row per HubSpot company record.
-- Domains are normalised for matching.

WITH source AS (

    SELECT *
    FROM {{ source('flinn_raw', 'HUBSPOT_COMPANIES') }}

),

cleaned AS (

    SELECT
        company_id,

        NULLIF(TRIM(company_name), '') AS company_name,

        NULLIF(LOWER(TRIM(domain)), '') AS domain,

        NULLIF(TRIM(industry), '') AS industry,

        NULLIF(TRIM(country), '') AS country,

        NULLIF(TRIM(number_of_employees), '') AS employee_band,

        CAST(create_date AS TIMESTAMP_NTZ) AS created_at

    FROM source

)

SELECT *
FROM cleaned
