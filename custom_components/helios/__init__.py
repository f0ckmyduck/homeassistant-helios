from datetime import timedelta
import ipaddress
import time
import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.const import CONF_HOST, CONF_NAME

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
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, "switch"))
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
        if speed >= 0 and speed <= 100:
            # Disable auto mode.
            self._client.set_variable('v00101', '1')
            self._auto = False

            # Set speed in percent.
            self._client.set_feature('v00103', speed)
            self._speed = speed
            self.fetchSpeed()

    def set_auto_mode(self, enabled: bool):
        self._client.set_variable('v00101', '0' if enabled else '1')
        self._auto = True
        self.fetchSpeed()

    def get_speed(self):
        return self._speed

    def is_auto(self) -> bool:
        return self._auto

    async def async_update(self, event_time):
        # Get the current operating mode.
        self._auto = self._client.get_variable("v00101", 1, conversion=int) == 0

        # Get the current speed.
        self.fetchSpeed()

    def fetchSpeed(self):
        self._speed = self._client.get_variable("v00103", 3, conversion=int)
        async_dispatcher_send(self._hass, SIGNAL_HELIOS_STATE_UPDATE)
