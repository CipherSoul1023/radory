"""Refine brokerage profile matching and ranking fields.

Revision ID: 0004_profile_refinement
Revises: 0003_unique_cleanup
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_profile_refinement"
down_revision: str | None = "0003_unique_cleanup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_brokerage_profiles_minimum_sqm", "brokerage_profiles", type_="check")
    op.drop_constraint("ck_brokerage_profiles_min_ideal", "brokerage_profiles", type_="check")
    op.drop_constraint("ck_brokerage_profiles_ideal_range", "brokerage_profiles", type_="check")
    op.drop_constraint("ck_brokerage_profiles_ideal_max", "brokerage_profiles", type_="check")

    op.alter_column("brokerage_profiles", "primary_metro", new_column_name="primary_market")
    op.alter_column(
        "brokerage_profiles",
        "minimum_sqm",
        new_column_name="min_transaction_size_sqm",
    )
    op.alter_column(
        "brokerage_profiles",
        "ideal_minimum_sqm",
        new_column_name="ideal_transaction_size_min_sqm",
    )
    op.alter_column(
        "brokerage_profiles",
        "ideal_maximum_sqm",
        new_column_name="ideal_transaction_size_max_sqm",
    )
    op.alter_column(
        "brokerage_profiles",
        "maximum_sqm",
        new_column_name="max_transaction_size_sqm",
    )
    op.alter_column("brokerage_profiles", "priorities", new_column_name="priority_factors")

    empty_json = sa.text("'[]'::jsonb")
    op.add_column(
        "brokerage_profiles",
        sa.Column(
            "custom_property_sectors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=empty_json,
            nullable=False,
        ),
    )
    op.add_column(
        "brokerage_profiles",
        sa.Column(
            "custom_submarkets",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=empty_json,
            nullable=False,
        ),
    )
    op.add_column(
        "brokerage_profiles",
        sa.Column(
            "custom_industries",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=empty_json,
            nullable=False,
        ),
    )

    op.execute(
        """
        UPDATE brokerage_profiles
        SET property_sectors = (
            SELECT COALESCE(jsonb_agg(
                CASE value
                    WHEN 'Office' THEN 'office'
                    WHEN 'Industrial / Logistics' THEN 'industrial_logistics'
                    WHEN 'Retail' THEN 'retail'
                    WHEN 'Other' THEN 'other'
                    ELSE value
                END
            ), '[]'::jsonb)
            FROM jsonb_array_elements_text(property_sectors) AS item(value)
        )
        """
    )
    op.execute(
        """
        UPDATE brokerage_profiles
        SET industries = (
            SELECT COALESCE(jsonb_agg(
                CASE value
                    WHEN 'Technology' THEN 'technology'
                    WHEN 'Financial services' THEN 'financial_services'
                    WHEN 'Professional services' THEN 'professional_services'
                    WHEN 'Healthcare' THEN 'healthcare'
                    WHEN 'Manufacturing' THEN 'manufacturing'
                    WHEN 'Logistics' THEN 'logistics'
                    WHEN 'Consumer goods' THEN 'retail_businesses'
                    WHEN 'Education' THEN 'professional_services'
                    WHEN 'Any industry' THEN 'any_industry'
                    ELSE value
                END
            ), '[]'::jsonb)
            FROM jsonb_array_elements_text(industries) AS item(value)
        )
        """
    )
    op.execute(
        """
        UPDATE brokerage_profiles
        SET opportunity_types = (
            SELECT COALESCE(jsonb_agg(
                CASE value
                    WHEN 'Expansion' THEN 'expansion'
                    WHEN 'Relocation' THEN 'relocation'
                    WHEN 'Renewal' THEN 'lease_renewal'
                    WHEN 'New market entry' THEN 'new_market_entry'
                    WHEN 'Consolidation' THEN 'consolidation'
                    WHEN 'Contraction / disposal' THEN 'contraction_space_disposal'
                    WHEN 'Sublease' THEN 'sublease'
                    ELSE value
                END
            ), '[]'::jsonb)
            FROM jsonb_array_elements_text(opportunity_types) AS item(value)
        )
        """
    )
    op.execute(
        """
        UPDATE brokerage_profiles
        SET prospecting_horizon = CASE prospecting_horizon
            WHEN '0–6 months' THEN 'up_to_6_months'
            WHEN '6–12 months' THEN 'up_to_12_months'
            WHEN '12–18 months' THEN 'up_to_18_months'
            WHEN '18–24 months' THEN 'up_to_24_months'
            WHEN '24+ months' THEN 'as_early_as_possible'
            ELSE prospecting_horizon
        END,
        country = 'South Africa'
        """
    )
    op.execute(
        """
        UPDATE brokerage_profiles
        SET priority_factors = COALESCE(
            (
                SELECT jsonb_agg(factor)
                FROM (
                    SELECT factor
                    FROM (
                        SELECT DISTINCT CASE
                            WHEN value LIKE 'submarket:%' THEN 'location_fit'
                            WHEN value LIKE 'industry:%' THEN 'industry_fit'
                            WHEN value LIKE 'deal:%' THEN 'deal_size_fit'
                            WHEN value LIKE 'opportunity:%' THEN 'opportunity_type_fit'
                            WHEN value LIKE 'timing:%' THEN 'timing'
                            ELSE NULL
                        END AS factor
                        FROM jsonb_array_elements_text(priority_factors) AS item(value)
                    ) AS mapped
                    WHERE factor IS NOT NULL
                    LIMIT 3
                ) AS limited
            ),
            '["evidence_strength"]'::jsonb
        )
        """
    )

    for column_name in (
        "custom_property_sectors",
        "custom_submarkets",
        "custom_industries",
    ):
        op.alter_column("brokerage_profiles", column_name, server_default=None)

    op.create_check_constraint(
        "ck_brokerage_profiles_min_transaction_size",
        "brokerage_profiles",
        "min_transaction_size_sqm > 0",
    )
    op.create_check_constraint(
        "ck_brokerage_profiles_min_ideal",
        "brokerage_profiles",
        "min_transaction_size_sqm <= ideal_transaction_size_min_sqm",
    )
    op.create_check_constraint(
        "ck_brokerage_profiles_ideal_range",
        "brokerage_profiles",
        "ideal_transaction_size_min_sqm <= ideal_transaction_size_max_sqm",
    )
    op.create_check_constraint(
        "ck_brokerage_profiles_ideal_max",
        "brokerage_profiles",
        "ideal_transaction_size_max_sqm <= max_transaction_size_sqm",
    )
    op.create_check_constraint(
        "ck_brokerage_profiles_country",
        "brokerage_profiles",
        "country = 'South Africa'",
    )


def downgrade() -> None:
    op.drop_constraint("ck_brokerage_profiles_country", "brokerage_profiles", type_="check")
    op.drop_constraint(
        "ck_brokerage_profiles_min_transaction_size", "brokerage_profiles", type_="check"
    )
    op.drop_constraint("ck_brokerage_profiles_min_ideal", "brokerage_profiles", type_="check")
    op.drop_constraint("ck_brokerage_profiles_ideal_range", "brokerage_profiles", type_="check")
    op.drop_constraint("ck_brokerage_profiles_ideal_max", "brokerage_profiles", type_="check")

    op.execute("UPDATE brokerage_profiles SET priority_factors = '[\"deal:Ideal-size deals\"]'")
    op.execute(
        """
        UPDATE brokerage_profiles
        SET prospecting_horizon = CASE prospecting_horizon
            WHEN 'up_to_6_months' THEN '0–6 months'
            WHEN 'up_to_12_months' THEN '6–12 months'
            WHEN 'up_to_18_months' THEN '12–18 months'
            WHEN 'up_to_24_months' THEN '18–24 months'
            WHEN 'as_early_as_possible' THEN '24+ months'
            ELSE prospecting_horizon
        END
        """
    )
    op.execute(
        """
        UPDATE brokerage_profiles
        SET property_sectors = (
            SELECT COALESCE(jsonb_agg(
                CASE value
                    WHEN 'office' THEN 'Office'
                    WHEN 'industrial_logistics' THEN 'Industrial / Logistics'
                    WHEN 'retail' THEN 'Retail'
                    WHEN 'other' THEN 'Other'
                    ELSE value
                END
            ), '[]'::jsonb)
            FROM jsonb_array_elements_text(property_sectors) AS item(value)
        ), industries = (
            SELECT COALESCE(jsonb_agg(
                CASE value
                    WHEN 'technology' THEN 'Technology'
                    WHEN 'financial_services' THEN 'Financial services'
                    WHEN 'professional_services' THEN 'Professional services'
                    WHEN 'healthcare' THEN 'Healthcare'
                    WHEN 'manufacturing' THEN 'Manufacturing'
                    WHEN 'logistics' THEN 'Logistics'
                    WHEN 'retail_businesses' THEN 'Consumer goods'
                    WHEN 'any_industry' THEN 'Any industry'
                    ELSE value
                END
            ), '[]'::jsonb)
            FROM jsonb_array_elements_text(industries) AS item(value)
        ), opportunity_types = (
            SELECT COALESCE(jsonb_agg(
                CASE value
                    WHEN 'expansion' THEN 'Expansion'
                    WHEN 'relocation' THEN 'Relocation'
                    WHEN 'lease_renewal' THEN 'Renewal'
                    WHEN 'new_market_entry' THEN 'New market entry'
                    WHEN 'consolidation' THEN 'Consolidation'
                    WHEN 'contraction_space_disposal' THEN 'Contraction / disposal'
                    WHEN 'sublease' THEN 'Sublease'
                    ELSE value
                END
            ), '[]'::jsonb)
            FROM jsonb_array_elements_text(opportunity_types) AS item(value)
        )
        """
    )

    op.drop_column("brokerage_profiles", "custom_industries")
    op.drop_column("brokerage_profiles", "custom_submarkets")
    op.drop_column("brokerage_profiles", "custom_property_sectors")
    op.alter_column("brokerage_profiles", "priority_factors", new_column_name="priorities")
    op.alter_column(
        "brokerage_profiles",
        "max_transaction_size_sqm",
        new_column_name="maximum_sqm",
    )
    op.alter_column(
        "brokerage_profiles",
        "ideal_transaction_size_max_sqm",
        new_column_name="ideal_maximum_sqm",
    )
    op.alter_column(
        "brokerage_profiles",
        "ideal_transaction_size_min_sqm",
        new_column_name="ideal_minimum_sqm",
    )
    op.alter_column(
        "brokerage_profiles",
        "min_transaction_size_sqm",
        new_column_name="minimum_sqm",
    )
    op.alter_column("brokerage_profiles", "primary_market", new_column_name="primary_metro")
    op.create_check_constraint(
        "ck_brokerage_profiles_minimum_sqm", "brokerage_profiles", "minimum_sqm >= 0"
    )
    op.create_check_constraint(
        "ck_brokerage_profiles_min_ideal",
        "brokerage_profiles",
        "minimum_sqm <= ideal_minimum_sqm",
    )
    op.create_check_constraint(
        "ck_brokerage_profiles_ideal_range",
        "brokerage_profiles",
        "ideal_minimum_sqm <= ideal_maximum_sqm",
    )
    op.create_check_constraint(
        "ck_brokerage_profiles_ideal_max",
        "brokerage_profiles",
        "ideal_maximum_sqm <= maximum_sqm",
    )
