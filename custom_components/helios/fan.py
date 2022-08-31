from homeassistant.core import callback
from typing import Any
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from homeassistant.components.fan import (
    FanEntity,
)

from .const import (
    DOMAIN,
    SIGNAL_HELIOS_STATE_UPDATE
)

async def async_setup_entry(hass, entry, async_add_entities):
    state_proxy = hass.data[DOMAIN]["state_proxy"]
    name = hass.data[DOMAIN]["name"]
    async_add_entities([HeliosFan(state_proxy, name)])

# TODO
# Set supported_features attributes
class HeliosFan(FanEntity):
    def __init__(self, state_proxy, name):
        self._state_proxy = state_proxy
        self._name = name

    @property
    def should_poll(self):
        return False

    async def async_added_to_hass(self):
        async_dispatcher_connect(
            self.hass, SIGNAL_HELIOS_STATE_UPDATE, self._update_callback
        )

    @callback
    def _update_callback(self):
        self.async_schedule_update_ha_state(True)


    def set_percentage(self, percentage: int) -> None:
        self._state_proxy.set_speed(percentage)

    def turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        self._state_proxy.set_speed(percentage)

    @property
    def name(self):
        return self._name

    @property
    def is_on(self) -> bool:
        speed = self._state_proxy.get_speed()
        return speed > 0

    @property
    def speed(self) -> str:
        speed = self._state_proxy.get_speed()
        return speed

