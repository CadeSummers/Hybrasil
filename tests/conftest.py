# SPDX-FileCopyrightText: 2026 Cade Summers
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Suite-wide settings.

Every workbook loader reads the live Google Sheet by default.  The tests must
not depend on a credential or the network, and should see the same data on
every run, so they read the committed snapshot in data/ instead
(hybrasil/data/snapshot.py, SOURCE_ENV).
"""

import os

os.environ.setdefault("HYBRASIL_DATA_SOURCE", "snapshot")
