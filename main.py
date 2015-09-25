#!/usr/bin/python

from redis import Redis
from jinja2 import Environment, PackageLoader
import os
from subprocess import call
import signal
import time

env = Environment(loader=PackageLoader('haproxy', 'templates'))
POLL_TIMEOUT = 5

signal.signal(signal.SIGCHLD, signal.SIG_IGN)


def get_services():
    client = Redis(
        host=os.environ['REDIS_HOST'],
        port=int(os.environ.get('REDIS_PORT', 6379)),
        db=6
    )
    """
    route_map = {
        'service_name': {
            'frontend': set([
                'test.in',
                'test.com',
            ]),
            'backend': set([
                '1.1.1.1:8000',
                '1.1.1.2:8001',
            ])
        }
    }
    """
    route_map = {}
    for key in client.keys("routes:*"):
        _, service, hosts, id = key.split(':')
        route_pair = route_map.setdefault(service, {})
        for host in hosts.split(','):
            # map hostname
            route_pair.setdefault('frontend', set([])).add(host)
        # map ip:port
        route_pair.setdefault('backend', set([])).add(
            tuple(client.get(key).split(':')))
    return route_map


def generate_config(services):
    template = env.get_template('haproxy.cfg.tmpl')
    with open("/etc/haproxy.cfg", "w") as f:
        f.write(template.render(services=services))

if __name__ == "__main__":
    current_services = {}
    while True:
        try:
            services = get_services()

            if not services or services == current_services:
                time.sleep(POLL_TIMEOUT)
                continue

            print "config changed. reload haproxy"
            generate_config(services)
            ret = call(["./reload-haproxy.sh"])
            if ret != 0:
                print "reloading haproxy returned: ", ret
                time.sleep(POLL_TIMEOUT)
                continue
            current_services = services

        except Exception, e:
            print "Error:", e

        time.sleep(POLL_TIMEOUT)
