__author__ = 'esteele'

import socket
import conf
from phue import Bridge, PhueRequestTimeout
from pushover import Client

GREEN = 20389
RED = 65535
LIGHT_SET_OK=1
LIGHT_SET_FAILED_BRIDGE_COMMS=2


def send_pushover_notification(message, title):
    client = Client(conf.PUSHOVER_USER, api_token=conf.PUSHOVER_API_TOKEN)
    return client.send_message(message, title=title, html=1)


def set_lamp_state(is_late):
    try:
        b = Bridge(conf.HUE_BRIDGE_IP)
    except PhueRequestTimeout:
        return LIGHT_SET_FAILED_BRIDGE_COMMS
    except socket.error:
        return LIGHT_SET_FAILED_BRIDGE_COMMS

    b.set_light(conf.HUE_LIGHT_NAME, 'on', True)  # Make sure it's on
    b.set_light(conf.HUE_LIGHT_NAME, 'bri', 254)  # Max brightness
    if is_late:
        b.set_light(conf.HUE_LIGHT_NAME, 'hue', RED)
    else:
        b.set_light(conf.HUE_LIGHT_NAME, 'hue', GREEN)
    # Only stay on for 30 seconds
    b.set_light(conf.HUE_LIGHT_NAME, 'on', False, transitiontime=300)
    return LIGHT_SET_OK