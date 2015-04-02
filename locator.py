import threading
import time

__author__ = 'esteele'
import conf
import re
import subprocess
import multiprocessing


class ContactingThread(threading.Thread):
    NOT_FOUND = "not found"

    def __init__(self, ip_address, location_name, ping_count):
        self.ip_address = ip_address
        self.location_name = location_name
        self.ping_count = ping_count
        self.result = self.NOT_FOUND
        super(ContactingThread, self).__init__()

    def run(self):
        try:
            # Redirect stderr - we don't want spammage if the host is
            #  uncontactable
            output = subprocess.check_output(
                ["ping", "-c", str(self.ping_count), self.ip_address],
                stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            # Unable to ping, possibly because there's no route or
            #  because it can't resolve the address
            output = ""

        mo = re.search("(?P<recv_count>[0-9]+) packets received", output)
        if mo:
            recv_count = int(mo.group("recv_count"))
            if recv_count > 0:
                self.result = self.location_name


def locate(host_tuples, ping_period):
    """Each host tuple is (ip_address, location name)"""
    thread_list = []
    for ip, loc_name in host_tuples:
        t = ContactingThread(ip, loc_name, ping_period)
        thread_list.append(t)
        t.start()

    for t in thread_list:
        t.join()

    return sorted([t.result for t in thread_list
                   if t.result is not t.NOT_FOUND])


def report_location_changes(host_tuples, ping_period):
    last_location = locate(host_tuples, ping_period)
    while True:
        last_check_finish = time.time()
        current_location = locate(host_tuples, ping_period)
        current_check_duration = time.time() - last_check_finish
        if current_check_duration < conf.LOCATION_PING_PERIOD_SECS:
            # Finished too quick. Chances are the ping is failing fast and we
            #  should just throttle ourselves and wait before trying again.
            throttle_period_secs = \
                conf.LOCATION_PING_PERIOD_SECS - current_check_duration
            print "Ping failed fast - throttling for %.1f secs" %\
                  (throttle_period_secs,)
            time.sleep(throttle_period_secs)

        if last_location:
            print "Device was located in %s" % (last_location,),
            if last_location == current_location:
                print "and is still there"
            else:
                print "but moved to %s" % (current_location,)
        else:
            print "Device was not accessible",
            if current_location:
                # FIXME - nicely say when it's been in > 1 place
                print "but is now located in %s" % (current_location,)
            else:
                print "and is still inaccessible"

        last_location = current_location





if __name__ == "__main__":
    # print is_contactable("localhost", 2)
    # print locate(conf.ADDRESS_NAME_PAIR_LISTS, conf.LOCATION_PING_PERIOD_SECS)
    print report_location_changes(
        conf.ADDRESS_NAME_PAIR_LISTS, conf.LOCATION_PING_PERIOD_SECS)
