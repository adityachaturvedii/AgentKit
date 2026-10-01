"""Bounded OpenHarness-derived presentation, profile, and context adapters.

Derived from HKUDS/OpenHarness at commit
9b2efd795c6aa09f88b0c257d269a9e518da6ae7 under the MIT license.
These modules do not import the upstream runtime, authentication, tools, or
provider clients.
"""

UPSTREAM_REVISION = "9b2efd795c6aa09f88b0c257d269a9e518da6ae7"

from .backend import run_deterministic_demo
from .context import discover_context, render_context
from .profiles import PublicProviderProfile, resolve_profile

__all__ = [
    "PublicProviderProfile",
    "UPSTREAM_REVISION",
    "discover_context",
    "render_context",
    "resolve_profile",
    "run_deterministic_demo",
]
