"""Integration stubs for external services."""

from integrations.base import BaseIntegration
from integrations.notion_stub import NotionIntegration
from integrations.hubspot_stub import HubSpotIntegration

ALL_INTEGRATIONS = [NotionIntegration, HubSpotIntegration]
