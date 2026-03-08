"""DEPRECATED — merge logic has moved to reconciliation.py.

This module exists only for backward compatibility.  The merge operation
is now part of the reconciliation phase because in a linear single-agent
pipeline the merge is trivial and needs no post-merge verification.

Import `MergeError` from `ralph_pipeline.phases.reconciliation` instead.
"""

from ralph_pipeline.phases.reconciliation import MergeError  # noqa: F401

# Legacy alias
MergeVerifyError = MergeError
