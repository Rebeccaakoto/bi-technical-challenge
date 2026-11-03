
WITH source AS (
    SELECT *
    FROM {{ source('flinn_raw', 'BACKEND_EVENTS') }}
),

renamed AS (
    SELECT
        TRIM(EVENT_ID) AS event_id,
        TRIM(EVENT_NAME) AS event_name,
        EVENT_TIMESTAMP AS event_timestamp,
        TRY_PARSE_JSON(EVENT_PROPERTIES) AS properties
    FROM source
),

extracted AS (
    SELECT
        event_id,
        event_name,
        event_timestamp,
        TO_DATE(event_timestamp) AS event_date,

        properties:organization:id::VARCHAR
            AS organization_id,

        properties:user:id::VARCHAR
            AS user_id,

        LOWER(TRIM(properties:user:email::VARCHAR))
            AS user_email,

        properties:search:id::VARCHAR
            AS search_id

    FROM renamed
)

SELECT
    event_id,
    event_name,
    event_timestamp,
    event_date,
    organization_id,
    user_id,
    user_email,
    search_id

FROM extracted
