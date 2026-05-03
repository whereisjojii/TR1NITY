"""HTTP route groups for the ingestor."""

from . import firewall, health, waf, wazuh

__all__ = ["firewall", "health", "waf", "wazuh"]
