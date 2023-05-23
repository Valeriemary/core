"""Provide a way to label and categorize anything."""
from __future__ import annotations

from collections.abc import Iterable, MutableMapping
import dataclasses
from dataclasses import dataclass
from typing import cast

from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from . import device_registry as dr, entity_registry as er
from .typing import UNDEFINED, UndefinedType

DATA_REGISTRY = "label_registry"
EVENT_LABEL_REGISTRY_UPDATED = "label_registry_updated"
STORAGE_KEY = "core.label_registry"
STORAGE_VERSION_MAJOR = 1
SAVE_DELAY = 10


@dataclass(frozen=True)
class LabelEntry:
    """Label Registry Entry."""

    label_id: str
    name: str
    normalized_name: str
    description: str | None = None
    color: str | None = None
    icon: str | None = None


class LabelRegistry:
    """Class to hold a registry of labels."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the label registry."""
        self.hass = hass
        self.labels: MutableMapping[str, LabelEntry] = {}
        self._store = hass.helpers.storage.Store(
            STORAGE_VERSION_MAJOR,
            STORAGE_KEY,
            atomic_writes=True,
        )
        self._normalized_name_label_idx: dict[str, str] = {}
        self.children: dict[str, set[str]] = {}

    @callback
    def async_get_label(self, label_id: str) -> LabelEntry | None:
        """Get label by id."""
        return self.labels.get(label_id)

    @callback
    def async_get_label_by_name(self, name: str) -> LabelEntry | None:
        """Get label by name."""
        normalized_name = normalize_label_name(name)
        if normalized_name not in self._normalized_name_label_idx:
            return None
        return self.labels[self._normalized_name_label_idx[normalized_name]]

    @callback
    def async_list_labels(self) -> Iterable[LabelEntry]:
        """Get all labels."""
        return self.labels.values()

    @callback
    def async_get_or_create(self, name: str) -> LabelEntry:
        """Get or create an label."""
        if label := self.async_get_label_by_name(name):
            return label
        return self.async_create(name)

    @callback
    def _generate_id(self, name: str) -> str:
        """Initialize ID."""
        suggestion = suggestion_base = slugify(name)
        tries = 1
        while suggestion in self.labels:
            tries += 1
            suggestion = f"{suggestion_base}_{tries}"
        return suggestion

    @callback
    def async_create(
        self,
        name: str,
        *,
        color: str | None = None,
        icon: str | None = None,
        description: str | None = None,
    ) -> LabelEntry:
        """Create a new label."""
        normalized_name = normalize_label_name(name)

        if self.async_get_label_by_name(name):
            raise ValueError(f"The name {name} ({normalized_name}) is already in use")

        label = LabelEntry(
            color=color,
            description=description,
            icon=icon,
            label_id=self._generate_id(name),
            name=name,
            normalized_name=normalized_name,
        )
        self.labels[label.label_id] = label
        self._normalized_name_label_idx[normalized_name] = label.label_id
        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_LABEL_REGISTRY_UPDATED,
            {"action": "create", "label_id": label.label_id},
        )
        return label

    @callback
    def async_delete(self, label_id: str) -> None:
        """Delete label."""
        label = self.labels[label_id]

        # Clean up all references
        dr.async_get(self.hass).async_clear_label_id(label_id)
        er.async_get(self.hass).async_clear_label_id(label_id)

        del self.labels[label_id]
        del self._normalized_name_label_idx[label.normalized_name]

        self.hass.bus.async_fire(
            EVENT_LABEL_REGISTRY_UPDATED, {"action": "remove", "label_id": label_id}
        )

        self.async_schedule_save()

    @callback
    def async_update(
        self,
        label_id: str,
        color: str | None | UndefinedType = UNDEFINED,
        description: str | None | UndefinedType = UNDEFINED,
        icon: str | None | UndefinedType = UNDEFINED,
        name: str | UndefinedType = UNDEFINED,
    ) -> LabelEntry:
        """Update name of label."""
        old = self.labels[label_id]
        changes = {
            attr_name: value
            for attr_name, value in (
                ("color", color),
                ("description", description),
                ("icon", icon),
            )
            if value is not UNDEFINED and getattr(old, attr_name) != value
        }

        normalized_name = None

        if name is not UNDEFINED and name != old.name:
            normalized_name = normalize_label_name(name)
            if normalized_name != old.normalized_name and self.async_get_label_by_name(
                name
            ):
                raise ValueError(
                    f"The name {name} ({normalized_name}) is already in use"
                )

            changes["name"] = name
            changes["normalized_name"] = normalized_name

        if not changes:
            return old

        new = self.labels[label_id] = dataclasses.replace(old, **changes)
        if normalized_name is not None:
            self._normalized_name_label_idx[
                normalized_name
            ] = self._normalized_name_label_idx.pop(old.normalized_name)

        self.async_schedule_save()
        self.hass.bus.async_fire(
            EVENT_LABEL_REGISTRY_UPDATED, {"action": "update", "label_id": label_id}
        )

        return new

    async def async_load(self) -> None:
        """Load the label registry."""
        data = await self._store.async_load()
        labels: MutableMapping[str, LabelEntry] = {}

        if data is not None:
            for label in data["labels"]:
                normalized_name = normalize_label_name(label["name"])
                labels[label["label_id"]] = LabelEntry(
                    color=label["color"],
                    description=label["description"],
                    icon=label["icon"],
                    label_id=label["label_id"],
                    name=label["name"],
                    normalized_name=normalized_name,
                )
                self._normalized_name_label_idx[normalized_name] = label["label_id"]

        self.labels = labels

    @callback
    def async_schedule_save(self) -> None:
        """Schedule saving the label registry."""
        self._store.async_delay_save(self._data_to_save, SAVE_DELAY)

    @callback
    def _data_to_save(self) -> dict[str, list[dict[str, str | None]]]:
        """Return data of label registry to store in a file."""
        return {
            "labels": [
                {
                    "color": entry.color,
                    "description": entry.description,
                    "icon": entry.icon,
                    "label_id": entry.label_id,
                    "name": entry.name,
                }
                for entry in self.labels.values()
            ]
        }


@callback
def async_get(hass: HomeAssistant) -> LabelRegistry:
    """Get label registry."""
    return cast(LabelRegistry, hass.data[DATA_REGISTRY])


async def async_load(hass: HomeAssistant) -> None:
    """Load label registry."""
    assert DATA_REGISTRY not in hass.data
    hass.data[DATA_REGISTRY] = LabelRegistry(hass)
    await hass.data[DATA_REGISTRY].async_load()


def normalize_label_name(label_name: str) -> str:
    """Normalize an label name by removing whitespace and case folding."""
    return label_name.casefold().replace(" ", "")
