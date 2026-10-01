"""OpenData Sentinel: civic open-data quality assurance."""

from civic_data_qa.engine import run_checks
from civic_data_qa.models import Dataset, Finding, RunResult

__version__ = "0.4.0"
__all__ = ["Dataset", "Finding", "RunResult", "__version__", "run_checks"]
