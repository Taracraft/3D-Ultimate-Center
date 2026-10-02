import asyncio

from core.common import utc_now
from core.event_bus import EventBus
from core.events import StudioEvent


async def test_event_bus_delivers_topic_and_wildcard() -> None:
    bus = EventBus()
    topic_stream = bus.subscribe("asset.analysis.completed")
    wildcard_stream = bus.subscribe("*")

    topic_task = asyncio.create_task(anext(topic_stream))
    wildcard_task = asyncio.create_task(anext(wildcard_stream))
    await asyncio.sleep(0)

    event = StudioEvent(
        topic="asset.analysis.completed",
        sequence=1,
        timestamp=utc_now(),
        payload={"asset_id": "asset_test"},
    )
    await bus.publish(event)

    assert await topic_task == event
    assert await wildcard_task == event
    await topic_stream.aclose()
    await wildcard_stream.aclose()