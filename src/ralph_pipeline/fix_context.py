"""Domain context loading for fix prompts.

.. deprecated::
    This module has been consolidated into :mod:`ralph_pipeline.context_refresh`.
    Import from there instead. This module re-exports for backward compatibility.
"""

from ralph_pipeline.context_refresh import (  # noqa: F401
    load_domain_context,
    load_type_config,
)
