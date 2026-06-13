"""Store Profile layer (Sprint 6.5).

Typed StoreProfile dataclass + descriptive dimension detection. See
``agent_outputs/ds-architect-store-profile-layer-proposal.md`` and
``agent_outputs/implementation-manager-s6_5-store-profile-layer-plan.md``
for the architectural rationale.

T1 ships the dataclass + 4 skeleton detectors (taxonomy / business_stage /
business_model / data_depth). T2 fills in the sub-vertical token
classifier. T3 fills cadence + seasonality. T4 fills gate calibration +
wires consumers. T5 flips ``ENGINE_V2_STORE_PROFILE`` ON.
"""

from .types import (  # noqa: F401
    BusinessModel,
    BusinessStage,
    CadenceBaseline,
    DataDepth,
    GateCalibration,
    MeasurementContext,
    ProfileProvenance,
    SeasonalityContext,
    StoreProfile,
    Taxonomy,
)
from .builder import build_store_profile  # noqa: F401
