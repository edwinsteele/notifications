__author__ = 'esteele'
import conf
import re
import subprocess
import multiprocessing


def is_contactable(args):
    """Takes a single argument so it can be run in a map"""
    ip_address, name, ping_count = args
    output = subprocess.check_output(
        ["ping", "-c", str(ping_count), ip_address])
    mo = re.search("(?P<recv_count>[0-9]+) packets received", output)
    if mo:
        recv_count = int(mo.group("recv_count"))
        if recv_count > 0:
            return name
    return 0


def locate(host_tuples, ping_period):
    """Each host tuple is (ip_address, location name)"""
    [ht.append(ping_period) for ht in host_tuples]
    pool = multiprocessing.Pool()
    host_tuples = [("localhost", "kitchen", 3),
        ("localhostzz", "roof", 3)]
    try:
        result = pool.map(is_contactable, host_tuples)
    except subprocess.CalledProcessError:
        pass
    return result




if __name__ == "__main__":
    # print is_contactable("localhost", 2)
    print locate(conf.ADDRESS_NAME_PAIR_LISTS, conf.LOCATION_PING_PERIOD_SECS)