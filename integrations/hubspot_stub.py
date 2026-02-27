"""HubSpot CRM integration stub — logs actions but does nothing."""

import os
from integrations.base import BaseIntegration


class HubSpotIntegration(BaseIntegration):
    name = "HubSpot"
    description = "Synka pipeline-deals till HubSpot CRM"

    def __init__(self):
        self.api_key = os.getenv("HUBSPOT_API_KEY", "")
        self.enabled = bool(self.api_key)

    def push_procurement(self, procurement: dict) -> bool:
        if not self.enabled:
            print(f"[HubSpot] Stub: would push '{procurement.get('title', '')}'")
            return False
        # TODO: Implement actual HubSpot API push
        print(f"[HubSpot] Push: {procurement.get('title', '')}")
        return True

    def sync_status(self) -> dict:
        if not self.api_key:
            return {"connected": False, "message": "HUBSPOT_API_KEY ej konfigurerad i .env"}
        return {"connected": True, "message": "API-nyckel konfigurerad (stubb — ej implementerad)"}
