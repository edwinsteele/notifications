import argparse
from datetime import datetime, timedelta
import itertools
import logging
import requests
import conf
import notifier

BASE_URL = "http://realtime.grofsoft.com/tripview/realtime?routes=%s&type=dtva"
DEFAULT_LATENESS_THRESHOLD_MINS = 5
SEND_NOTIFICATION_ALWAYS = "always"
SEND_NOTIFICATION_AUTO = "auto"
SEND_NOTIFICATION_NEVER = "never"


class Trip(object):
    def __init__(self, trip_id, first_departure_time, last_departure_time):
        self.trip_id = trip_id
        self.start_time_str = "unknown"
        self.start_time_timedelta = timedelta.max
        self.start_loc_int = -1
        self.start_loc_str = "unknown"
        self.location = "unknown"
        self.alert = None
        self.offset_tuples = []
        self.first_departure_time = first_departure_time
        self.last_departure_time = last_departure_time

    def populate_estimated_arrival_times(self):
        start_time = self.start_time_timedelta
        if start_time == timedelta.max:
            # There was no delay data available for the vehicle when the
            #  trip was created which should only occur when the train has
            #  actually arrived at its destination, and in this case we don't
            #  care about arrival times.
            self.est_scheduled_arrival_earliest = timedelta.max
            self.est_scheduled_arrival_latest = timedelta.max

        if self.start_loc_str in conf.transit_times:
            min_transit, max_transit = conf.transit_times[self.start_loc_str]
            self.est_scheduled_arrival_earliest = start_time + min_transit
            self.est_scheduled_arrival_latest = start_time + max_transit
        else:
            # If we can't find a transit time, return results that have no
            #  chance of being in the schedule.
            self.est_scheduled_arrival_earliest = timedelta.max
            self.est_scheduled_arrival_latest = timedelta.max

    def is_current(self):
        """Arrives at departure station in the future"""
        return now_as_timedelta() < self.est_scheduled_arrival_latest

    def arrives_in_departure_window(self):
        """Arrives at departure station in the window"""
        return \
            (self.first_departure_time <
             self.est_scheduled_arrival_earliest <
             self.last_departure_time) or \
            (self.first_departure_time <
             self.est_scheduled_arrival_latest <
             self.last_departure_time)

    def estimate_delay_at_boarding_station(self):
        possible_delay_tuples = list(itertools.dropwhile(
            lambda x: x[0] < self.est_scheduled_arrival_earliest,
            self.offset_tuples))
        # The first delay number will be close enough, so let's use that
        if possible_delay_tuples:
            return possible_delay_tuples[0][1]
        else:
            return 0

    def delay_description(self):
        estimated_delay = self.estimate_delay_at_boarding_station()
        if estimated_delay > 0:
            return "%sm late" % (estimated_delay,)
        elif estimated_delay < 0:
            return "%sm early" % (abs(estimated_delay),)
        else:
            return "on-time"

    def is_running_late(self, lateness_threshold_mins):
        return self.estimate_delay_at_boarding_station() >= \
            lateness_threshold_mins

    def short_summary(self):
        if not (self.is_current() and self.arrives_in_departure_window()):
            s = ""
        else:
            s = "%s: Scheduled arrival: %s-%s currently at %s (%s from %s)." % \
                (self.delay_description(),
                 self.est_scheduled_arrival_earliest,
                 self.est_scheduled_arrival_latest,
                 self.location,
                 self.start_time_str,
                 self.start_loc_str)
            if self.alert:
                s += " Alert: %s" % (self.alert,)
        return s

    def full_summary(self):
        s = ""
        if not self.arrives_in_departure_window():
            s += "[Arrives outside departure window] "
        if not self.is_current():
            s += "[In the past] "

        s += "Trip %s. %s from %s (%s). Currently at %s." \
             " Estimated arrival: %s-%s. Alert: %s" % \
            (self.trip_id,
             self.start_time_str,
             self.start_loc_str,
             self.delay_description(),
             self.location,
             self.est_scheduled_arrival_earliest,
             self.est_scheduled_arrival_latest,
             self.alert)
        return s


def hhmm_string_to_timedelta(s):
    """hh:mm to timedelta"""
    return timedelta(0, 0, 0, 0, *map(int, reversed(s.split(":"))))


def now_as_timedelta():
    n = datetime.now()
    return timedelta(hours=n.hour, minutes=n.minute)


def extract_trip(j, trip_id, fdt, ldt):
    t = Trip(trip_id, fdt, ldt)
    delay_data = filter(lambda x: x["tripId"] == trip_id, j["delays"])
    #transposition_data = filter(
    #    lambda x: x["tripId"] == trip_id, j["transpositions"])
    vehicle_data = filter(lambda x: x["tripId"] == trip_id, j["vehicles"])
    alert_data = filter(lambda x: x["tripId"] == trip_id, j["alerts"])

    if delay_data:
        t.start_time_str = delay_data[0]["start"]
        # "hh:mm" to timedelta
        t.start_time_timedelta = \
            hhmm_string_to_timedelta(delay_data[0]["start"])
        t.start_loc_int = int(delay_data[0]["stopId"])
        t.start_loc_str = conf.stop_ids.get(
            t.start_loc_int, "Unknown")
        # offsets is a string of comma sep list of alternating times and delays
        # e.g. "14:15,16,17:10,14,17:42,13,18:25,11,19:57,10,20:20,9"
        # Convert to list of tuples of datetime.timedelta & delay as int
        #
        # Sometimes offsets is not present in the delay data
        if "offsets" in delay_data[0]:
            offsets_raw_list = delay_data[0]["offsets"].split(",")
        else:
            offsets_raw_list = []
        t.offset_tuples = zip(
            [hhmm_string_to_timedelta(x)
             for x in (itertools.islice(offsets_raw_list, 0, None, 2))],
            map(int, itertools.islice(offsets_raw_list, 1, None, 2))
        )

    if vehicle_data:
        t.location = vehicle_data[0]["lp"].rsplit(":", 2)[0]
    if alert_data:
        if "body" in alert_data[0]:
            t.alert = alert_data[0]["body"]
        else:
            t.alert = alert_data[0]["title"]

    t.populate_estimated_arrival_times()
    return t


def main(fdt, ldt, lateness_threshold_mins, send_notification, no_lights):
    r = requests.get(BASE_URL % (conf.ROUTES,))
    j = r.json()

    logging.debug("Retrieved at: %s",
                  datetime.fromtimestamp(j["timestamp"]).ctime())
    # Save the realtime data for troubleshooting and verification
    logging.debug("JSON data follows:")
    logging.debug(r.text)

    logging.debug("Looking for arrivals between %s and %s", fdt, ldt)
    # Trains only appear in the vehicles list once they have actually departed.
    # Trains that are past their departure time ("start") but have not left
    #  their origin are not listed in vehicles until they've actually left
    #  the station.
    trips = []
    for tripId in [v["tripId"] for v in j["vehicles"]
                   if v["route"] == conf.ROUTES]:
        trips.append(extract_trip(j, tripId, fdt, ldt))

    notification_lines = []
    short_summary_lines = []
    full_summary_lines = []
    trains_are_running_late = False
    for t in trips:
        if t.is_current() and t.arrives_in_departure_window():
            if t.is_running_late(lateness_threshold_mins):
                trains_are_running_late = True
                notification_lines.append(t.short_summary())
            short_summary_lines.append(t.short_summary())
            full_summary_lines.append(t.full_summary())
        else:
            full_summary_lines.append(t.full_summary())

    if len(notification_lines) == 0:
        notification_subject = "All trains on time"
    elif len(notification_lines) == 1:
        notification_subject = "1 train running late"
    else:
        notification_subject = "%s trains running late" % \
                               (len(notification_lines),)

    logging.info(notification_subject)
    notification_lines.append("Retrieved at: %s" %
                              (datetime.fromtimestamp(j["timestamp"]).ctime(),))
    notification_message = "\n".join(notification_lines)

    if send_notification == SEND_NOTIFICATION_ALWAYS or \
            (send_notification != SEND_NOTIFICATION_NEVER and
             trains_are_running_late):
        logging.info("Sending pushover notification. Subject: %s",
                     notification_subject)
        logging.info("Notification message: %s", notification_message)
        request = notifier.send_pushover_notification(notification_message,
                                                      notification_subject)
        logging.debug("Request is %s", request)
    else:
        logging.info("Not sending pushover notification")

    if not no_lights:
        notifier.set_lamp_state(trains_are_running_late)
    else:
        logging.debug("Not turning on lights because --no_lights cmdline param")

    logging.debug("--- Short summary start ---")
    logging.debug(short_summary_lines)
    logging.debug("--- Full summary start ---")
    logging.debug(full_summary_lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--first_departure_time", help="as hh:mm")
    parser.add_argument("--last_departure_time", help="as hh:mm")
    parser.add_argument("--lateness_threshold_mins", type=int,
                        default=DEFAULT_LATENESS_THRESHOLD_MINS,
                        help="Trains delayed by more than or equal to this "
                             "number of minutes are deemed late")
    parser.add_argument("--send-notification", default=SEND_NOTIFICATION_AUTO,
                        choices=[SEND_NOTIFICATION_ALWAYS,
                                 SEND_NOTIFICATION_AUTO,
                                 SEND_NOTIFICATION_NEVER])
    parser.add_argument("--no_lights", action="store_true", default=False)
    parser.add_argument("--verbose", "-v", action="count")
    args = parser.parse_args()
    if args.first_departure_time:
        first_departure_time = \
            hhmm_string_to_timedelta(args.first_departure_time)
    else:
        first_departure_time = now_as_timedelta()
    if args.last_departure_time:
        last_departure_time = \
            hhmm_string_to_timedelta(args.last_departure_time)
    else:
        last_departure_time = now_as_timedelta() + timedelta(minutes=60)

    # Optionally log to disk instead of stdout
    logfile = getattr(conf, "LOGFILE", None)

    if args.verbose is None:
        logging.basicConfig(level=logging.WARNING, filename=logfile)
    elif args.verbose == 1:
        logging.basicConfig(level=logging.INFO, filename=logfile)
    else:
        logging.basicConfig(level=logging.DEBUG, filename=logfile)

    main(first_departure_time,
         last_departure_time,
         args.lateness_threshold_mins,
         args.send_notification,
         args.no_lights)
