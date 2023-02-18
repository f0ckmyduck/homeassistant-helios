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
    hass.data[DOMAIN] = {
        "client": client,
        "state_proxy": state_proxy,
        "name": entry.data[CONF_NAME]
    }

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor"))
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "fan"))

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
        self._sensors = {}

        self._hass = hass
        self._client = client

        self._device = self.get_helios_var("v00000", 30)
        self._kwl_mac = self.get_helios_var("v00002", 18)
        self._sw_version = self.get_helios_var("v01101", 7)

        if isinstance(self._kwl_mac, str):
            self._base_unique_id = format_mac(self._kwl_mac)

        else:
            self._base_unique_id = None

        # TODO error checking
        self.register_sensor('v00101', 1, False)
        self.register_sensor('v00102', 1, False)

        # Register the Fan speed and Auto mode sensors
        self.register_sensor('v00101', 0, True)
        self.register_sensor('v00102', 0, True)

        self._listener_queue_send = Queue()
        self._listener_queue_receive = Queue()
        self._listener = Thread(target=self.update)
        self._listener.start()
        logging.debug("Started listener thread")

    def kill(self):
        self._listener_queue_send.put(_sentinel)
        self._listener.join()
        logging.debug("Joined listener thread")

    def get_helios_var(self, name: str, size: int) -> str | None:
        var = None

        try:
            var = func_timeout(1,
                               self._client.get_variable,
                               args=(name, size))

            if not isinstance(var, str):
                logging.warning("Did not receive a return variable:" +
                                str(var) + " -> " + name + "(" +
                                str(size) + ")")

        except (FunctionTimedOut):
            logging.warning("Getting variable " + name + "(" + str(size) +
                            ") timed out")

        except Exception as e:
            logging.warning("Getting variable " + name + "(" + str(size) +
                            ") failed with the following exception: " +
                            str(e))

        return var

    def set_helios_var(self, name: str, var: int) -> bool:
        try:
            self._client.set_variable(name, var)

        except Exception as e:
            logging.warning("Setting variable " + name + "(" + str(var) +
                            ") failed with the following exception: " + str(e))
            return False

        return True

    def is_auto(self):
        return int(self._sensors[("v00101", 1, False)]) == 0

    def get_speed(self):
        return int(self._sensors[("v00102", 1, False)])

    def set_speed(self, speed: int):
        self.set_auto_mode(False)
        self._sensors[('v00102', 0, True)] = speed

    def set_auto_mode(self, enabled: bool):
        self._sensors[('v00101', 0, True)] = (0 if enabled else 1)

    def register_sensor(self, name, var, is_setable) -> bool:
        if not is_setable:
            #Check if the sensors even exists.
            temp = self.get_helios_var(name, var)

            if isinstance(temp, str):
                if temp != "-":
                    self._sensors[(name, var, is_setable)] = temp
                    return True
        else:
            self._sensors[(name, var, is_setable)] = 0
            return True

        return False

    async def async_update(self, event_time):
        if self._listener_queue_send.empty:
            self._listener_queue_send.put_nowait(self._sensors)

        try:
            self._sensors = self._listener_queue_receive.get_nowait()

        except Empty:
            return

        async_dispatcher_send(self._hass, SIGNAL_HELIOS_STATE_UPDATE)
        logging.debug("Update Fetched")

    # Sets the retrieves all sensor values and caches them in sensors
    def update(self):
        while True:
            temp = self._listener_queue_send.get()

            # Break the infinite loop.
            if temp == _sentinel:
                break

            self._sensors = temp

            # Update all sensors which are registered
            for i in self._sensors:
                logging.debug("Updating: " + str(i[0]) + " - " + str(i[1]))

                # If it is not setable, fetch the value of the sensor.
                if not i[2]:
                    temp = self.get_helios_var(i[0], i[1])

                    if isinstance(temp, str):
                        self._sensors[(i[0], i[1], i[2])] = temp

                else:
                    # TODO error handling
                    self.set_helios_var(i[0], self._sensors[(i[0], i[1], i[2])]) 

            if self._listener_queue_receive.empty:
                self._listener_queue_receive.put_nowait(self._sensors)
                logging.debug("Next sensor state update ready")
