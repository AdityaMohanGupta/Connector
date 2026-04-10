from typing import Any

import httpx

from app.config import Settings, get_settings


class GraphClient:
    def __init__(self, access_token: str, settings: Settings | None = None) -> None:
        self.access_token = access_token
        self.settings = settings or get_settings()

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        headers = {**self.headers, **kwargs.pop("headers", {})}
        async with httpx.AsyncClient(base_url=self.settings.graph_base_url, timeout=30) as client:
            response = await client.request(method, path, headers=headers, **kwargs)
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {"ok": True}
        return response.json()

    async def list_folders(self) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            "/me/mailFolders",
            params={"$select": "id,displayName,totalItemCount,unreadItemCount", "$top": 50},
        )
        return data.get("value", [])

    async def list_messages(self, folder_id: str = "inbox", top: int = 20) -> list[dict[str, Any]]:
        folder = folder_id or "inbox"
        data = await self._request(
            "GET",
            f"/me/mailFolders/{folder}/messages",
            params={
                "$top": min(max(top, 1), 50),
                "$orderby": "receivedDateTime desc",
                "$select": "id,subject,from,receivedDateTime,isRead,bodyPreview",
            },
        )
        return data.get("value", [])

    async def get_message(self, message_id: str) -> dict[str, Any]:
        return await self._request(
            "GET",
            f"/me/messages/{message_id}",
            params={
                "$select": "id,subject,from,toRecipients,ccRecipients,receivedDateTime,isRead,bodyPreview,body"
            },
            headers={"Prefer": 'outlook.body-content-type="text"'},
        )

    async def send_mail(self, payload: dict[str, Any]) -> dict[str, Any]:
        recipients = [{"emailAddress": {"address": address}} for address in payload.get("to", [])]
        cc_recipients = [{"emailAddress": {"address": address}} for address in payload.get("cc", [])]
        body = {
            "message": {
                "subject": payload["subject"],
                "body": {"contentType": "Text", "content": payload["body"]},
                "toRecipients": recipients,
                "ccRecipients": cc_recipients,
            },
            "saveToSentItems": payload.get("save_to_sent_items", True),
        }
        return await self._request("POST", "/me/sendMail", json=body)

    async def list_events(self, top: int = 20) -> list[dict[str, Any]]:
        data = await self._request(
            "GET",
            "/me/events",
            params={
                "$top": min(max(top, 1), 50),
                "$orderby": "start/dateTime",
                "$select": "id,subject,bodyPreview,start,end,location,attendees,organizer",
            },
        )
        return data.get("value", [])

    def _event_body(self, payload: dict[str, Any]) -> dict[str, Any]:
        body: dict[str, Any] = {}
        if payload.get("subject") is not None:
            body["subject"] = payload["subject"]
        if payload.get("body") is not None:
            body["body"] = {"contentType": "Text", "content": payload.get("body") or ""}
        if payload.get("start") is not None:
            body["start"] = {
                "dateTime": payload["start"],
                "timeZone": payload.get("time_zone", "India Standard Time"),
            }
        if payload.get("end") is not None:
            body["end"] = {
                "dateTime": payload["end"],
                "timeZone": payload.get("time_zone", "India Standard Time"),
            }
        if payload.get("location") is not None:
            body["location"] = {"displayName": payload.get("location") or ""}
        if payload.get("attendees") is not None:
            body["attendees"] = [
                {"emailAddress": {"address": address}, "type": "required"}
                for address in payload.get("attendees", [])
            ]
        return body

    async def create_event(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/me/events", json=self._event_body(payload))

    async def update_event(self, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PATCH", f"/me/events/{event_id}", json=self._event_body(payload))

    async def cancel_event(self, event_id: str, comment: str = "") -> dict[str, Any]:
        return await self._request("DELETE", f"/me/events/{event_id}")
