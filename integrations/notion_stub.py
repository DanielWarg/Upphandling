"""Notion integration stub — logs actions but does nothing."""

import os
from integrations.base import BaseIntegration


class NotionIntegration(BaseIntegration):
    name = "Notion"
    description = "Synka upphandlingar till en Notion-databas"

    def __init__(self):
        self.api_key = os.getenv("NOTION_API_KEY", "")
        self.enabled = bool(self.api_key)

    def push_procurement(self, procurement: dict) -> bool:
        if not self.enabled:
            print(f"[Notion] Stub: would push '{procurement.get('title', '')}'")
            return False
        # TODO: Implement actual Notion API push
        print(f"[Notion] Push: {procurement.get('title', '')}")
        return True

    def sync_status(self) -> dict:
        if not self.api_key:
            return {"connected": False, "message": "NOTION_API_KEY ej konfigurerad i .env"}
        return {"connected": True, "message": "API-nyckel konfigurerad (stubb — ej implementerad)"}
