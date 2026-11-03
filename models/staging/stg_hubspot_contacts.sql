-- One row per HubSpot contact. Email is normalised so it can be matched
-- to backend user emails (the bridge between the two systems).

with source as (

    select * from {{ source('flinn_raw', 'HUBSPOT_CONTACTS') }}

)

select
    contact_id,
    first_name,
    last_name,
    lower(trim(email))                          as email,
    split_part(lower(trim(email)), '@', 2)      as email_domain,
    job_title,
    hubspot_company_id,
    lifecycle_stage,
    create_date::timestamp_ntz                  as created_at

from source