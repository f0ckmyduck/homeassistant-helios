from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import SensorEntity, STATE_CLASS_MEASUREMENT

from .const import (DOMAIN, SCAN_INTERVAL, SIGNAL_HELIOS_STATE_UPDATE)


# Add some of the available sensors to the entity list.
async def async_setup_entry(hass, entry, async_add_entities):
    client = hass.data[DOMAIN]["client"]
    name = hass.data[DOMAIN]["name"] + ' '
    state_proxy = hass.data[DOMAIN]["state_proxy"]

    # Add all the installation independent sensors which every unit should support.
    entity_data = [
        # Temperature sensors
        ("Outside Air", "v00104", 7, TEMP_CELSIUS, "mdi:thermometer"),
        ("Supply Air", "v00105", 7, TEMP_CELSIUS, "mdi:thermometer"),
        ("Extract Air", "v00106", 7, TEMP_CELSIUS, "mdi:thermometer"),
        ("Exhaust Air", "v00107", 7, TEMP_CELSIUS, "mdi:thermometer"),
        ("Extract Air Humidity", "v02136", 2, "%", "mdi:water-percent"),
        ("Supply Air Speed", "v00348", 4, "rpm", "mdi:fan"),
        ("Extract Air Speed", "v00349", 4, "rpm", "mdi:fan"),

        # Fanspeed
        ("Fan Speed", "v00102", 1, "Step", "mdi:fan"),
    ]

    # Try to add of the possible external sensors.
    for i in range(0, 8):
        entity_data.append(("External CO2 " + str(i), "v00" + str(128 + i), 4,
                            "ppm", "mdi:molecule-co2"))

    for i in range(0, 8):
        entity_data.append(("External Humidity " + str(i), "v00" + str(111 + i),
                           4, "%", "mdi:water-percent"))

    for i in range(0, 8):
        entity_data.append(("External Temperature " + str(i), "v00" + str(119 + i),
                            7, TEMP_CELSIUS, "mdi:thermometer"))

    for i in range(0, 8):
        entity_data.append(("Gas concentration " + str(i), "v00" + str(136 + i),
                           4, "ppm", "mdi:gas-cylinder"))

    # Try to register them in the update function of the stateproxy
    # and if that succeeds, add them to the entity list.
    entries = []
    for i in entity_data:
        if state_proxy.register_sensor(i[1], i[2], False):
            entries.append(
                HeliosSensor(client, state_proxy, name + i[0], i[1], i[2],
                             i[3], i[4]))

    # Add all entries from the list above.
    async_add_entities(entries, update_before_add=False)


class HeliosSensor(SensorEntity):
    def __init__(self, client, state_proxy, name, var, var_length, units,
                 icon):
        self._state_proxy = state_proxy
        self._attr_unique_id = state_proxy._base_unique_id + "-" + var

        self._state = None
        self._name = name
        self._variable = var
        self._var_length = var_length
        self._units = units
        self._icon = icon
        self._client = client
        self._attr_state_class = STATE_CLASS_MEASUREMENT

    def update(self):
        self._state = self._state_proxy._sensors[(self._variable,
                                                  self._var_length, False)]

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return self._icon

    @property
    def unit_of_measurement(self):
        return self._units
