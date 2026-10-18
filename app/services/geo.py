"""Compatibility shim: the implementation lives in app.ai.geo."""
from ..ai.geo import *  # noqa: F401,F403
from ..ai.geo import (canonical_city_exact, in_india_scope, is_india, normalize_city,  # noqa: F401
                      same_region, suggest_cities)
