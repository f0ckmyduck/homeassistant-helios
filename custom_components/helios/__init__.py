from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.device_registry import format_mac
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

    # Initialize via configuration.yaml if needed
    hass.data[DOMAIN]["config"] = config.get(DOMAIN) or {}
    return True

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    client = eazyctrl.EazyController(config_entry.data[CONF_HOST])
    state_proxy = HeliosStateProxy(hass, client)

    # Set global data dictionary
    hass.data[DOMAIN] = {"client": client, "state_proxy": state_proxy, "name": config_entry.data[CONF_NAME]}

    hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, "sensor"))
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(config_entry, "fan"))

    async_track_time_interval(hass, state_proxy.async_update, SCAN_INTERVAL)
    await state_proxy.async_update(0)

    return True

def get_helios_var(client: eazyctrl.EazyController, name: str, size: int) -> str | None:
    var = None

    try:
        var = func_timeout(1, client.get_variable, args=(name, size))

    except Exception as e:
        logging.warning("Getting variable " + name + "(" + str(size) + ") failed with the following exception: " + str(e))

    except (FunctionTimedOut):
        logging.warning("Getting variable " + name + "(" + str(size) + ") timed out")

    if not isinstance(var, str):
        logging.warning("Did not receive a return variable:" + str(var) + " -> " + name + "(" + str(size) + ")")

    return var


class HeliosStateProxy:
    def __init__(self, hass, client):
        self._device = get_helios_var(client, "v00000", 30)
        self._kwl_mac = get_helios_var(client, "v00002", 18)
        self._sw_version = get_helios_var(client, "v01101", 7)

        if isinstance(self._kwl_mac, str):
            self._base_unique_id = format_mac(self._kwl_mac)

        else:
            self._base_unique_id = None

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
        # Enable or disable auto mode.
        temp = get_helios_var(self._client, "v00101", 1)
        if temp is not None:
            self._auto = (int(temp) == 0)

        else:
            self._auto = False

        # Get the current speed.
        self.fetchSpeed()

    def fetchSpeed(self):
        self._speed = get_helios_var(self._client, "v00103", 3)

        async_dispatcher_send(self._hass, SIGNAL_HELIOS_STATE_UPDATE)
