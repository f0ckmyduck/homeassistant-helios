from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.device_registry import format_mac
from homeassistant.const import CONF_HOST, CONF_NAME

from func_timeout import func_timeout, FunctionTimedOut
from queue import Queue, Empty
from threading import Thread
import logging

from .const import (
    DOMAIN,
    SIGNAL_HELIOS_STATE_UPDATE,
    SCAN_INTERVAL,
)

import eazyctrl


_sentinel = object()

async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})

    # Initialize via configuration.yaml if needed
    hass.data[DOMAIN]["config"] = config.get(DOMAIN) or {}
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    client = eazyctrl.EazyController(entry.data[CONF_HOST])
    state_proxy = HeliosStateProxy(hass, client)

    # Set global data dictionary
    hass.data[DOMAIN] = {"client": client, "state_proxy": state_proxy, "name": entry.data[CONF_NAME]}

    hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, "sensor"))
    hass.async_create_task(hass.config_entries.async_forward_entry_setup(entry, "fan"))

    async_track_time_interval(hass, state_proxy.async_update, SCAN_INTERVAL)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "fan")

    hass.data[DOMAIN]["state_proxy"].kill()
    hass.data[DOMAIN].pop("state_proxy")
    hass.data[DOMAIN].pop("client")
    hass.data[DOMAIN].pop("name")
    return True

class HeliosStateProxy:
    def __init__(self, hass, client):
        self._webserver_busy = False

        self._sensors = {}

        self._hass = hass
        self._client = client
        self._auto = True 
        self._speed = None

        self._device = self.get_helios_var("v00000", 30)
        self._kwl_mac = self.get_helios_var("v00002", 18)
        self._sw_version = self.get_helios_var("v01101", 7)

        if isinstance(self._kwl_mac, str):
            self._base_unique_id = format_mac(self._kwl_mac)

        else:
            self._base_unique_id = None

        # TODO error checking
        self.register_sensor("v00101", 1)
        self.register_sensor("v00103", 3)

        self._listener_queue_send = Queue()
        self._listener_queue_receive = Queue()
        self._listener = Thread(target=self.update)
        self._listener.start()
        #  logging.info("Started listener thread")

    def kill(self):
        self._listener_queue_send.put(_sentinel)
        self._listener.join()
        #  logging.info("Joined listener thread")

    def get_helios_var(self, name: str, size: int) -> str | None:
        var = None

        try:
            if self._webserver_busy:
                return var

            self._webserver_busy = True
            var = func_timeout(1, self._client.get_variable, args=(name, size))
            self._webserver_busy = False

        except Exception as e:
            logging.warning("Getting variable " + name + "(" + str(size) + ") failed with the following exception: " + str(e))

        except (FunctionTimedOut):
            logging.warning("Getting variable " + name + "(" + str(size) + ") timed out")

        if not isinstance(var, str):
            logging.warning("Did not receive a return variable:" + str(var) + " -> " + name + "(" + str(size) + ")")

        return var

    def set_helios_var(self, name: str, var: int) -> bool:
        try:
            if self._webserver_busy:
                return False

            self._webserver_busy = True
            self._client.set_variable(name, var)
            self._webserver_busy = False

        except Exception as e:
            logging.warning("Setting variable " + name + "(" + str(var) + ") failed with the following exception: " + str(e))
            return False

        return True

    def is_auto(self):
        return self._auto

    def set_speed(self, speed: int):
        if not isinstance(speed, int):
            speed = 50
            
        if speed >= 0 and speed <= 100:
            # Disable auto mode.
            self.set_auto_mode(False)

            # Set speed in 4 different stages because god forbid someone uses a percentage.
            # Avoid 0 because the easycontrol server doesn't do anything at that step.
            self.set_helios_var('v00102', int(speed / 25) + 1)

    def set_auto_mode(self, enabled: bool):
        self.set_helios_var('v00101', 0 if enabled else 1)
        self._auto = enabled 

    def register_sensor(self, name, size) -> bool:
        temp = self.get_helios_var(name, size)

        if isinstance(temp, str):
            if temp != "-":
                self._sensors[(name, size)] = temp
                return True

        return False


    async def async_update(self, event_time):
        self._listener_queue_send.put_nowait(self._sensors)

        try:
            self._sensors = self._listener_queue_receive.get_nowait()

        except Empty:
            return

        async_dispatcher_send(self._hass, SIGNAL_HELIOS_STATE_UPDATE)
        #  logging.warning("Update Fetched")
        

    def update(self):
        while True:
            temp = self._listener_queue_send.get()

            if temp == _sentinel:
                break

            self._sensors = temp

            # Update all sensors which are registered
            for index in self._sensors:
                #  logging.warning("Updating: " + str(index[0]) + " - " + str(index[1]))
                temp = self.get_helios_var(index[0], index[1])

                if isinstance(temp, str):
                    self._sensors[(index[0], index[1])] = temp

            self._auto = int(self._sensors[("v00101", 1)]) == 0
            self._speed = int(self._sensors[("v00103", 3)])

            self._listener_queue_receive.put(self._sensors)
            #  logging.warning("Next sensor state update ready")

