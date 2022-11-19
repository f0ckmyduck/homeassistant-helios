from homeassistant.core import callback
from typing import Any
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from homeassistant.components.fan import (
    SUPPORT_SET_SPEED,
    FanEntity,
)
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    SIGNAL_HELIOS_STATE_UPDATE
)

async def async_setup_entry(hass, entry, async_add_entities):
    state_proxy = hass.data[DOMAIN]["state_proxy"]
    name = hass.data[DOMAIN]["name"]
    async_add_entities([HeliosFan(state_proxy, name)])

class HeliosFan(FanEntity):

    def __init__(self, state_proxy, name):
        self._attr_icon = "mdi:air-filter"
        self._attr_unique_id = state_proxy._base_unique_id + "-Fan"
        
        self._state_proxy = state_proxy
        self._name = name


    @property
    def should_poll(self):
        return False

    #  @property
    #  def device_info(self) -> DeviceInfo | None:
        #  return DeviceInfo(
            #  identifiers={
                #  (DOMAIN, self._attr_unique_id)
            #  },
            #  name=self._name,
            #  manufacturer="Helios",
            #  model=self._state_proxy.device,
            #  sw_version=self._state_proxy._sw_version,
        #  )

    async def async_added_to_hass(self):
        async_dispatcher_connect(
            self.hass, SIGNAL_HELIOS_STATE_UPDATE, self._update_callback
        )

    @callback
    def _update_callback(self):
        self.async_schedule_update_ha_state(True)

    def set_percentage(self, percentage: int) -> None:
        self._state_proxy.set_speed(percentage)

    def turn_on(self, percentage: int, preset_mode: str, **kwargs: Any) -> None:
        self._state_proxy.set_speed(percentage)

    def turn_off(self, **kwargs: Any) -> None:
        self._state_proxy.set_auto_mode(True);

    @property
    def name(self):
        return self._name

    @property
    def is_on(self) -> bool:
        return not self._state_proxy.is_auto()

    @property
    def speed(self) -> str:
        return self._state_proxy.get_speed() * 25

    @property
    def supported_features(self) -> int:
        return SUPPORT_SET_SPEED

