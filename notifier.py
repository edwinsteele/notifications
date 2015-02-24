__author__ = 'esteele'

import conf
from phue import Bridge
from pushover import Client


def send_pushover_notification(message, title):
    client = Client(conf.PUSHOVER_USER, api_token=conf.PUSHOVER_API_TOKEN)
    return client.send_message(message, title=title)


def set_lamp_state(is_late):
    b = Bridge(conf.HUE_BRIDGE_IP)
    b.set_light(conf.HUE_LIGHT_NAME, 'on', True)  # Make sure it's on
    b.set_light(conf.HUE_LIGHT_NAME, 'bri', 254)  # Max brightness
    if is_late:
        b.set_light(conf.HUE_LIGHT_NAME, 'hue', 65535)
    else:
        b.set_light(conf.HUE_LIGHT_NAME, 'hue', 20389)
    # Only stay on for 30 seconds
    b.set_light(conf.HUE_LIGHT_NAME, 'on', False, transitiontime=300)