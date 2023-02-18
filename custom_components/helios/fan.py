from homeassistant.core import callback
from typing import Any
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from homeassistant.components.fan import (
    FanEntity,
    FanEntityFeature,
)
from homeassistant.helpers.entity import DeviceInfo

from .const import (DOMAIN, SIGNAL_HELIOS_STATE_UPDATE)

Helios_Presets = ["Low", "Mid Low", "Mid High", "High"]

async def async_setup_entry(hass, entry, async_add_entities):
    state_proxy = hass.data[DOMAIN]["state_proxy"]
    name = hass.data[DOMAIN]["name"]
    async_add_entities([HeliosFan(state_proxy, name)])


class HeliosFan(FanEntity):

    def __init__(self, state_proxy, name):
        self._attr_icon = "mdi:air-filter"
        self._attr_unique_id = state_proxy._base_unique_id + "-Fan"
        self._attr_supported_features = FanEntityFeature.SET_SPEED | FanEntityFeature.PRESET_MODE
        self._attr_preset_modes = Helios_Presets

        self._state_proxy = state_proxy
        self._name = name

    @property
    def should_poll(self):
        return True

    @property
    def device_info(self) -> DeviceInfo | None:
        return DeviceInfo(
            identifiers={(DOMAIN, self._state_proxy._base_unique_id)},
            name=self._name,
            manufacturer="Helios",
            model=self._state_proxy._device,
            sw_version=self._state_proxy._sw_version,
        )

    async def async_added_to_hass(self):
        async_dispatcher_connect(self.hass, SIGNAL_HELIOS_STATE_UPDATE,
                                 self._update_callback)

    @callback
    def _update_callback(self):
        self.async_schedule_update_ha_state(True)

    def set_percentage(self, val: int) -> None:
        self._state_proxy.set_speed(val / 25)

    def turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs: Any) -> None:
        self._state_proxy.set_auto_mode(False)

        if preset_mode is not None:
            counter = 1
            for i in Helios_Presets:
                if i == preset_mode:
                    self._state_proxy.set_speed(counter)

                counter = counter + 1
        else:
            if percentage is not None:
                self._state_proxy.set_speed(percentage / 25)

    def turn_off(self, **kwargs: Any) -> None:
        self._state_proxy.set_auto_mode(True)

    @property
    def name(self) -> str | None:
        return self._name

    @property
    def is_on(self) -> bool:
        return not self._state_proxy.is_auto()

    @property
    def percentage_step(self) -> float:
        return 4

    @property
    def speed_count(self) -> int:
        return 4

    @property
    def percentage(self) -> int | None:
        return self._state_proxy.get_speed() * 25

    def set_preset_mode(self, preset_mode: str) -> None:
        counter = 1
        for i in Helios_Presets:
            if i == preset_mode:
                self._state_proxy.set_speed(counter)

            counter = counter + 1
        return 
