__author__ = 'esteele'

import conf
from pushover import Client


def send_pushover_notification(message, title):
    client = Client(conf.PUSHOVER_USER, api_token=conf.PUSHOVER_API_TOKEN)
    return client.send_message(message, title=title)





