from homeassistant import config_entries
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_NAME
import homeassistant.helpers.device_registry as dr

import eazyctrl

from .const import (
    DOMAIN,
    DEFAULT_NAME,
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    @property
    def schema(self):
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_HOST): str,
            }
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is not None:

            await self.async_set_unique_id(user_input[CONF_NAME])
            self._abort_if_unique_id_configured()

            #  try:

            #  except:
                #  return self.async_show_form(
                    #  step_id="user",
                    #  data_schema=self.schema,
                    #  errors={"base": "invalid_host"}
                #  )

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input
            )

            

        return self.async_show_form(step_id="user", data_schema=self.schema)
