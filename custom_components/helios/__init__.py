from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import CONF_HOST, CONF_NAME

from func_timeout import func_timeout, FunctionTimedOut
import logging

from .const import (
    DOMAIN,
    SIGNAL_HELIOS_STATE_UPDATE,
    SCAN_INTERVAL,
)

import eazyctrl

async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["config"] = config.get(DOMAIN) or {}
    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    host = config_entry.data[CONF_HOST]
    name = config_entry.data[CONF_NAME]

    client = eazyctrl.EazyController(host)
    state_proxy = HeliosStateProxy(hass, client)
    hass.data[DOMAIN] = {"client": client, "state_proxy": state_proxy, "name": name}

    hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, "sensor"))
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, "fan"))

    async_track_time_interval(hass, state_proxy.async_update, SCAN_INTERVAL)
    await state_proxy.async_update(0)
    return True

class HeliosStateProxy:
    def __init__(self, hass, client):
        self._hass = hass
        self._client = client
        self._auto = True 
        self._speed = None

    def set_speed(self, speed: int):
        if not isinstance(speed, int):
            speed = 50
            
        if speed >= 0 and speed <= 100:
            # Disable auto mode.
            self.set_auto_mode(False)

            # Set speed in 4 different stages because god forbid someone uses a percentage.
            # Avoid 0 because the easycontrol server doesn't do anything at that step.
            self._client.set_variable('v00102', int(speed / 25) + 1)
            self.fetchSpeed()

    def set_auto_mode(self, enabled: bool):
        self._client.set_variable('v00101', '0' if enabled else '1')
        self._auto = enabled 
        self.fetchSpeed()

    def get_speed(self):
        return self._speed

    def is_auto(self) -> bool:
        return self._auto

    async def async_update(self, event_time):
        # Get the current operating mode.
        try:
            self._auto = (int(str(func_timeout(1, self._client.get_variable, args=('v00101', 1)))) == 0)

        except(FunctionTimedOut):
            logging.warning("Sensor AutoMode (v00101) value fetch timed out!")

        # Get the current speed.
        self.fetchSpeed()

    def fetchSpeed(self):
        try:
            self._speed = int(str(func_timeout(1, self._client.get_variable, args=("v00103", 3))))

        except(FunctionTimedOut):
            logging.warning("Sensor FanSpeed (v00103) value fetch timed out!")

        async_dispatcher_send(self._hass, SIGNAL_HELIOS_STATE_UPDATE)
