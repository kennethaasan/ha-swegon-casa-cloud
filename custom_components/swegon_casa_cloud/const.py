"""Constants for the Swegon CASA cloud integration."""

from datetime import timedelta

DOMAIN = "swegon_casa_cloud"

CONF_APP_API_KEY = "app_api_key"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_THING_ID = "thing_id"

API_BASE_URL = "https://swegoncasa.com"
APP_USER_AGENT = (
    "fi.swegon.ahu2020.mobile.resident;1.0.0.248;248;"
    "Home Assistant;Linux;0"
)
MQTT_USER_AGENT = "?SDK=Android&Version=2.16.13"

DEFAULT_UPDATE_INTERVAL = timedelta(minutes=2)
MODE_REGISTER = 1039
# The app uses one continuous control value for normal modes and reserves low
# values for automatic/startup states. Reads return the same value that the app
# writes; this is not the 4x5001 operating-mode enum from the Modbus document.
MODE_TO_WRITE_VALUE = {
    "travelling": 5,
    "away": 35,
    "home": 65,
    "home_plus": 80,
    "boost": 100,
}
CONTROL_VALUE_TO_MODE = {
    1: "automatic",
    2: "starting",
    **{value: mode for mode, value in MODE_TO_WRITE_VALUE.items()},
}

# These virtual registers and meanings come directly from the mobile summary's
# UI rules. They must not be confused with similarly named 4x/3x Modbus
# registers from the physical-bus register list.
SUMMER_MODE_BOOST_REGISTER = 1043
SUMMER_MODE_SETTING_REGISTER = 1335
SUMMER_MODE_STATE_REGISTER = 2112
CONTROL_SOURCE_REGISTER = 2146
APPLICATION_REGISTER = 5042

SUMMER_MODE_SETTING = {
    0: "off",
    1: "auto",
    2: "auto_plus",
}

CONTROL_SOURCE = {
    0: "external_stopped",
    1: "external_travelling",
    2: "external_away",
    3: "external_home",
    4: "external_home_plus",
    5: "external_boost",
    7: "app_automatic",
}


def summer_mode_is_active(
    boost_level: int | None,
    state: int | None,
    control_value: int | None,
    application: int | None,
) -> bool | None:
    """Match the official app's active Summer mode boost visibility rule."""
    if (
        boost_level is None
        or state is None
        or control_value is None
        or application is None
    ):
        return None
    return (
        boost_level > 1
        and state == 5
        and control_value > 0
        and application == 0
    )


PLATFORMS = ["binary_sensor", "select", "sensor"]
