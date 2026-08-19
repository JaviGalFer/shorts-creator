"""Static provider capability registry for future media routing.

The registry contains no secrets and no dynamic availability checks. Runtime
credentials and provider implementation status remain outside this pure module.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from shorts_creator.contracts.visual_media import IMAGE, MEDIA_KINDS, VIDEO

STOCK = "STOCK"
GENERATED = "GENERATED"
MANUAL = "MANUAL"
SOURCE_TYPES: frozenset[str] = frozenset({STOCK, GENERATED, MANUAL})

SEARCH = "SEARCH"
GENERATE = "GENERATE"
INGEST = "INGEST"
QUERY_STRATEGIES: frozenset[str] = frozenset({SEARCH, GENERATE, INGEST})

AVAILABLE = "AVAILABLE"
CONDITIONAL = "CONDITIONAL"
PLANNED = "PLANNED"
DISABLED = "DISABLED"
RUNTIME_STATUSES: frozenset[str] = frozenset({
    AVAILABLE, CONDITIONAL, PLANNED, DISABLED,
})

DIRECT = "DIRECT"
CONDITIONAL_FIT = "CONDITIONAL"
UNSUPPORTED = "UNSUPPORTED"
UNDECLARED = "UNDECLARED"
VISUAL_FORM_FITS: frozenset[str] = frozenset({
    DIRECT, CONDITIONAL_FIT, UNSUPPORTED, UNDECLARED,
})

EXACT_FORMS: frozenset[str] = frozenset({
    "diagram", "infographic", "illustration", "painting",
})


@dataclass(frozen=True)
class ProviderCapability:
    capability_id: str
    provider: str
    media_kind: str
    source_type: str
    query_strategy: str
    runtime_status: str
    requires_api_key: bool
    visual_form_fit: Mapping[str, str]
    evidence_version: str | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "visual_form_fit",
            MappingProxyType(dict(self.visual_form_fit)),
        )


def _pexels_form_fit(*, photograph_fit: str) -> Mapping[str, str]:
    return MappingProxyType({
        "photograph": photograph_fit,
        **{form: UNSUPPORTED for form in EXACT_FORMS},
    })


PROVIDER_CAPABILITIES: tuple[ProviderCapability, ...] = (
    ProviderCapability(
        capability_id="wikimedia_commons.image.stock",
        provider="wikimedia_commons",
        media_kind=IMAGE,
        source_type=STOCK,
        query_strategy=SEARCH,
        runtime_status=AVAILABLE,
        requires_api_key=False,
        visual_form_fit={},
        evidence_version=None,
    ),
    ProviderCapability(
        capability_id="pixabay.image.stock",
        provider="pixabay",
        media_kind=IMAGE,
        source_type=STOCK,
        query_strategy=SEARCH,
        runtime_status=AVAILABLE,
        requires_api_key=True,
        visual_form_fit={},
        evidence_version=None,
    ),
    ProviderCapability(
        capability_id="pexels.photos.stock",
        provider="pexels",
        media_kind=IMAGE,
        source_type=STOCK,
        query_strategy=SEARCH,
        runtime_status=AVAILABLE,
        requires_api_key=True,
        visual_form_fit=_pexels_form_fit(photograph_fit=DIRECT),
        evidence_version="pexels-provider-fit-benchmark",
    ),
    ProviderCapability(
        capability_id="pexels.video.stock",
        provider="pexels",
        media_kind=VIDEO,
        source_type=STOCK,
        query_strategy=SEARCH,
        runtime_status=PLANNED,
        requires_api_key=True,
        visual_form_fit=_pexels_form_fit(photograph_fit=CONDITIONAL_FIT),
        evidence_version="pexels-provider-fit-benchmark",
    ),
)


def get_provider_capability(capability_id: str) -> ProviderCapability | None:
    """Return one static capability by id without I/O."""
    for capability in PROVIDER_CAPABILITIES:
        if capability.capability_id == capability_id:
            return capability
    return None


def get_visual_form_fit(
    capability: ProviderCapability,
    visual_form: str,
) -> str:
    """Return declared fit, without treating absent evidence as unsupported."""
    return capability.visual_form_fit.get(visual_form, UNDECLARED)
