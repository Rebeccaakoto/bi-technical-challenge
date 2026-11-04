-- One row per backend event. Cleans types, flattens event_properties into
-- columns and classifies events so later models can separate real product
-- usage from logins and admin activity.
--
-- event_properties only contains: user.id, organization.id (identical to the
-- top-level columns, so the top-level columns are used), user.email
-- (UserCreated only), search.id, search_result.id and label.id.

with source as (

    select * from {{ source('flinn_raw', 'BACKEND_EVENTS') }}

),

renamed as (

    select
        trim(event_id)                     as event_id,
        trim(event_name)                   as event_name,
        event_timestamp::timestamp_ntz     as event_at,
        trim(user_id)                      as user_id,
        trim(organization_id)              as organization_id,
        try_parse_json(event_properties)   as properties
    from source

),

extracted as (

    select
        event_id,
        event_name,
        event_at,
        to_date(event_at)                                    as event_date,
        organization_id,
        user_id,

        -- flattened event_properties
        lower(trim(properties:user:email::varchar))          as user_email,       -- UserCreated only
        properties:search:id::varchar                        as search_id,        -- Search* events
        properties:search_result:id::varchar                 as search_result_id, -- SearchResult* events
        properties:label:id::varchar                         as label_id,         -- Label* events

        -- classification
        case
            when event_name = 'TokenGenerated'                                then 'authentication'
            when event_name in ('UserCreated', 'UserUpdated',
                                'OrganizationCreated', 'OrganizationUpdated') then 'account_admin'
            when event_name like 'Search%'                                    then 'search'
            when event_name like 'Label%'                                     then 'label'
            else 'other'
        end                                                  as event_category,

        -- Assumption: "active" = a deliberate product action,
        -- not a login/token refresh or an account admin change
        event_name not in ('TokenGenerated', 'UserCreated', 'UserUpdated',
                           'OrganizationCreated', 'OrganizationUpdated') as is_product_usage

    from renamed

)

select
    event_id,
    event_name,
    event_at,
    event_date,
    organization_id,
    user_id,
    user_email,
    search_id,
    search_result_id,
    label_id,
    event_category,
    is_product_usage

from extracted