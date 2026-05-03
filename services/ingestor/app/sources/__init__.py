"""Source-specific parsers — each one converts a raw event to ECSEvent."""

from . import firewall, modsec, wazuh

__all__ = ["firewall", "modsec", "wazuh"]
