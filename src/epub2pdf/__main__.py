"""Allow running as `python -m epub2pdf`."""

import sys

from .cli import main

sys.exit(main())
