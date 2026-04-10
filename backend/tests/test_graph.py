from app.config import Settings
from app.graph import GraphClient


def test_graph_headers_include_bearer() -> None:
    client = GraphClient("access-token", Settings())
    assert client.headers["Authorization"] == "Bearer access-token"


def test_event_body_maps_graph_shape() -> None:
    client = GraphClient("access-token", Settings())
    body = client._event_body(
        {
            "subject": "Planning",
            "body": "Agenda",
            "start": "2026-04-10T10:00:00",
            "end": "2026-04-10T10:30:00",
            "time_zone": "India Standard Time",
            "location": "Room 1",
            "attendees": ["person@example.com"],
        }
    )
    assert body["subject"] == "Planning"
    assert body["start"]["timeZone"] == "India Standard Time"
    assert body["attendees"][0]["emailAddress"]["address"] == "person@example.com"
