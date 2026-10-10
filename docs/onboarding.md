# Brokerage onboarding

Radory's tenant-representation onboarding uses prepared South African market and
commercial-submarket datasets. A brokerage may submit no submarkets, but every
submitted `submarkets` value must exist in the backend allowlist.

`custom_submarkets` is a deprecated compatibility field retained in the database
and API response because migration `0004_profile_refinement` has already been
applied. Active clients must submit an empty list. The backend rejects non-empty
values, and the onboarding interface does not offer custom submarket creation.
