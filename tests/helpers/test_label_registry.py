"""Tests for the Label Registry."""
import re
from typing import Any

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import label_registry
from homeassistant.helpers.label_registry import (
    EVENT_LABEL_REGISTRY_UPDATED,
    STORAGE_KEY,
    STORAGE_VERSION_MAJOR,
    LabelRegistry,
    async_get,
    async_load,
)

from tests.common import async_capture_events, flush_store


async def test_list_labels(hass: HomeAssistant) -> None:
    """Make sure that we can read label."""
    registry = label_registry.async_get(hass)
    labels = registry.async_list_labels()

    assert len(list(labels)) == len(registry.labels)


async def test_create_label(hass: HomeAssistant) -> None:
    """Make sure that we can create labels."""
    update_events = async_capture_events(hass, EVENT_LABEL_REGISTRY_UPDATED)
    registry = label_registry.async_get(hass)
    label = registry.async_create(
        name="My Label",
        color="#FF0000",
        icon="mdi:test",
        description="This label is for testing",
    )

    assert label.label_id == "my_label"
    assert label.name == "My Label"
    assert label.color == "#FF0000"
    assert label.icon == "mdi:test"
    assert label.description == "This label is for testing"

    assert len(registry.labels) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 1
    assert update_events[0].data == {
        "action": "create",
        "label_id": label.label_id,
    }


async def test_create_label_with_name_already_in_use(hass: HomeAssistant) -> None:
    """Make sure that we can't create an label with a name already in use."""
    update_events = async_capture_events(hass, EVENT_LABEL_REGISTRY_UPDATED)
    registry = label_registry.async_get(hass)
    registry.async_create("mock")

    with pytest.raises(
        ValueError, match=re.escape("The name mock (mock) is already in use")
    ):
        registry.async_create("mock")

    await hass.async_block_till_done()

    assert len(registry.labels) == 1
    assert len(update_events) == 1


async def test_create_label_with_id_already_in_use(hass: HomeAssistant) -> None:
    """Make sure that we can't create an label with a name already in use."""
    registry = label_registry.async_get(hass)
    label = registry.async_create("Label")

    updated_label = registry.async_update(label.label_id, name="Renamed Label")
    assert updated_label.label_id == label.label_id

    second_label = registry.async_create("Label")
    assert label.label_id != second_label.label_id
    assert second_label.label_id == "label_2"


async def test_delete_label(hass: HomeAssistant) -> None:
    """Make sure that we can delete an label."""
    update_events = async_capture_events(hass, EVENT_LABEL_REGISTRY_UPDATED)
    registry = label_registry.async_get(hass)
    label = registry.async_create("Label")
    assert len(registry.labels) == 1

    registry.async_delete(label.label_id)

    assert not registry.labels

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "label_id": label.label_id,
    }
    assert update_events[1].data == {
        "action": "remove",
        "label_id": label.label_id,
    }


async def test_delete_non_existing_label(hass: HomeAssistant) -> None:
    """Make sure that we can't delete an label that doesn't exist."""
    registry = label_registry.async_get(hass)
    registry.async_create("mock")

    with pytest.raises(KeyError):
        registry.async_delete("")

    assert len(registry.labels) == 1


async def test_update_label(hass: HomeAssistant) -> None:
    """Make sure that we can update labels."""
    update_events = async_capture_events(hass, EVENT_LABEL_REGISTRY_UPDATED)
    registry = label_registry.async_get(hass)
    label = registry.async_create("Mock")

    assert len(registry.labels) == 1
    assert label.label_id == "mock"
    assert label.name == "Mock"
    assert label.color is None
    assert label.icon is None
    assert label.description is None

    updated_label = registry.async_update(
        label.label_id,
        name="Updated",
        color="#FFFFFF",
        icon="mdi:update",
        description="Updated description",
    )

    assert updated_label != label
    assert updated_label.label_id == "mock"
    assert updated_label.name == "Updated"
    assert updated_label.color == "#FFFFFF"
    assert updated_label.icon == "mdi:update"
    assert updated_label.description == "Updated description"

    assert len(registry.labels) == 1

    await hass.async_block_till_done()

    assert len(update_events) == 2
    assert update_events[0].data == {
        "action": "create",
        "label_id": label.label_id,
    }
    assert update_events[1].data == {
        "action": "update",
        "label_id": label.label_id,
    }


async def test_update_label_with_same_data(hass: HomeAssistant) -> None:
    """Make sure that we can reapply the same data to the label and it won't update."""
    update_events = async_capture_events(hass, EVENT_LABEL_REGISTRY_UPDATED)
    registry = label_registry.async_get(hass)
    label = registry.async_create(
        "mock",
        color="#FFFFFF",
        icon="mdi:test",
        description="Description",
    )

    udpated_label = registry.async_update(
        label_id=label.label_id,
        name="mock",
        color="#FFFFFF",
        icon="mdi:test",
        description="Description",
    )
    assert label == udpated_label

    await hass.async_block_till_done()

    # No update event
    assert len(update_events) == 1
    assert update_events[0].data == {
        "action": "create",
        "label_id": label.label_id,
    }


async def test_update_label_with_same_name_change_case(hass: HomeAssistant) -> None:
    """Make sure that we can reapply the same name with a different case to the label."""
    registry = label_registry.async_get(hass)
    label = registry.async_create("mock")

    updated_label = registry.async_update(label.label_id, name="Mock")

    assert updated_label.name == "Mock"
    assert updated_label.label_id == label.label_id
    assert updated_label.normalized_name == label.normalized_name
    assert len(registry.labels) == 1


async def test_update_label_with_name_already_in_use(hass: HomeAssistant) -> None:
    """Make sure that we can't update an label with a name already in use."""
    registry = label_registry.async_get(hass)
    label1 = registry.async_create("mock1")
    label2 = registry.async_create("mock2")

    with pytest.raises(
        ValueError, match=re.escape("The name mock2 (mock2) is already in use")
    ):
        registry.async_update(label1.label_id, name="mock2")

    assert label1.name == "mock1"
    assert label2.name == "mock2"
    assert len(registry.labels) == 2


async def test_update_label_with_normalized_name_already_in_use(
    hass: HomeAssistant,
) -> None:
    """Make sure that we can't update an label with a normalized name already in use."""
    registry = label_registry.async_get(hass)
    label1 = registry.async_create("mock1")
    label2 = registry.async_create("M O C K 2")

    with pytest.raises(
        ValueError, match=re.escape("The name mock2 (mock2) is already in use")
    ):
        registry.async_update(label1.label_id, name="mock2")

    assert label1.name == "mock1"
    assert label2.name == "M O C K 2"
    assert len(registry.labels) == 2


async def test_load_labels(hass: HomeAssistant) -> None:
    """Make sure that we can load/save data correctly."""
    registry = label_registry.async_get(hass)
    label1 = registry.async_create(
        "Label One",
        color="#FF000",
        icon="mdi:one",
        description="This label is label one",
    )
    label2 = registry.async_create(
        "Label Two",
        color="#000FF",
        icon="mdi:two",
        description="This label is label two",
    )

    assert len(registry.labels) == 2

    registry2 = LabelRegistry(hass)
    await flush_store(registry._store)
    await registry2.async_load()

    assert len(registry2.labels) == 2
    assert list(registry.labels) == list(registry2.labels)

    label1_registry2 = registry2.async_get_or_create("Label One")
    assert label1_registry2.label_id == label1.label_id
    assert label1_registry2.name == label1.name
    assert label1_registry2.color == label1.color
    assert label1_registry2.description == label1.description
    assert label1_registry2.icon == label1.icon
    assert label1_registry2.normalized_name == label1.normalized_name

    label2_registry2 = registry2.async_get_or_create("Label Two")
    assert label2_registry2.name == label2.name
    assert label2_registry2.color == label2.color
    assert label2_registry2.description == label2.description
    assert label2_registry2.icon == label2.icon
    assert label2_registry2.normalized_name == label2.normalized_name


@pytest.mark.parametrize("load_registries", [False])
async def test_loading_label_from_storage(
    hass: HomeAssistant, hass_storage: Any
) -> None:
    """Test loading stored labels on start."""
    hass_storage[STORAGE_KEY] = {
        "version": STORAGE_VERSION_MAJOR,
        "data": {
            "labels": [
                {
                    "color": "#FFFFFF",
                    "description": None,
                    "icon": "mdi:test",
                    "label_id": "one",
                    "name": "One",
                }
            ]
        },
    }

    await async_load(hass)
    registry = async_get(hass)

    assert len(registry.labels) == 1


async def test_getting_label(hass: HomeAssistant) -> None:
    """Make sure we can get the labels by name."""
    registry = label_registry.async_get(hass)
    label = registry.async_get_or_create("Mock1")
    label2 = registry.async_get_or_create("mock1")
    label3 = registry.async_get_or_create("mock   1")

    assert label == label2
    assert label == label3
    assert label2 == label3

    get_label = registry.async_get_label_by_name("M o c k 1")
    assert get_label == label

    get_label = registry.async_get_label(label.label_id)
    assert get_label == label


async def test_async_get_label_by_name_not_found(hass: HomeAssistant) -> None:
    """Make sure we return None for non-existent labels."""
    registry = label_registry.async_get(hass)
    registry.async_create("Mock1")

    assert len(registry.labels) == 1

    assert registry.async_get_label_by_name("non_exist") is None
