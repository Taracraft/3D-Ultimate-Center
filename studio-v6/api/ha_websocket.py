"""Home Assistant WebSocket bridge for V6 worker events."""

from __future__ import annotations

import asyncio
from dataclasses import asdict

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from core.event_bus import EventBus


@websocket_api.websocket_command(
    {
        vol.Required("type"): "printer_control_center/v1/subscribe_events",
        vol.Optional("topic", default="*"): str,
    }
)
@websocket_api.async_response
async def websocket_subscribe_events(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
    event_bus: EventBus,
) -> None:
    topic = msg["topic"]
    connection.send_result(msg["id"], {"subscribed": True, "topic": topic})

    async def forward() -> None:
        async for event in event_bus.subscribe(topic):
            connection.send_event(msg["id"], asdict(event))

    task = asyncio.create_task(forward())
    connection.subscriptions[msg["id"]] = task.cancel


def register_v1_websocket(hass: HomeAssistant, event_bus: EventBus) -> None:
    async def handler(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict,
    ) -> None:
        await websocket_subscribe_events(hass, connection, msg, event_bus)

    websocket_api.async_register_command(
        hass,
        handler,
        {
            vol.Required("type"): "printer_control_center/v1/subscribe_events",
            vol.Optional("topic", default="*"): str,
        },
    )