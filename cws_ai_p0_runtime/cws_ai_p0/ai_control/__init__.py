# SPDX-License-Identifier: GPL-3.0-or-later
"""Experimental CWS Boost AI control core.

The package is intentionally isolated from the render critical path.
Importing it must not register handlers, start networking, or mutate a scene.
"""

AI_CONTROL_VERSION = 1
