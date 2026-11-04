-- One row per HubSpot deal. Casts types and derives a single deal_status
-- from the is_closed / is_closed_won flags.

with source as (

    select * from {{ source('flinn_raw', 'HUBSPOT_DEALS') }}

)

select
    deal_id,
    deal_name,
    pipeline,
    deal_type,
    hubspot_company_id,
    amount::number(18, 2)                               as amount,
    currency,

    is_closed::boolean                                  as is_closed,
    is_closed_won::boolean                              as is_closed_won,
    case
        when is_closed_won::boolean then 'won'
        when is_closed::boolean     then 'lost'
        else 'open'
    end                                                 as deal_status,

    create_date::timestamp_ntz                          as created_at,
    close_date::timestamp_ntz                           as closed_at,

    date_entered_pre_pitch::timestamp_ntz               as entered_pre_pitch_at,
    date_entered_pitching::timestamp_ntz                as entered_pitching_at,
    date_entered_product_testing::timestamp_ntz         as entered_product_testing_at,
    date_entered_price_offering::timestamp_ntz          as entered_price_offering_at,
    date_entered_contract_negotiation::timestamp_ntz    as entered_contract_negotiation_at,
    date_entered_closed_won::timestamp_ntz              as entered_closed_won_at,
    date_entered_closed_lost::timestamp_ntz             as entered_closed_lost_at

from source