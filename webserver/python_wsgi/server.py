# coding: utf-8

from __future__ import unicode_literals
from pymongo import MongoClient
import web
import logging
import sys
import re
import netaddr
import socket
from json import dumps

web.config.debug = False

# Logging
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout, format='%(asctime)s :: %(levelname)s :: %(message)s')

urls = (
    '/', 'req_ip',
    '/(.*)', 'find_ip',
)
app = web.application(urls, globals())

def search_in_db(ip):
    result = {}
    result['ip'] = ip

    ip_to_long = int(netaddr.IPAddress(ip))

    db = MongoClient("mongodb://localhost")['geoip']

    ips = db.ips
    ip_exists = ips.find_one(
        {
            'start': { '$lte': ip_to_long },
            'end': { '$gte': ip_to_long }
        },
        {
            'geoname_id': 1,
            'is_anonymous_proxy': 1,
            'is_satellite_provider': 1,
            'latitude': 1,
            'longitude':1,
            'postal_code': 1,
            '_id': 0
        })

    if ip_exists:
        print('Found {} in DB'.format(ip))

        for k, v in ip_exists.iteritems():
            result[k] = str(v)

        # Geo data
        geos = db.geos
        geo = geos.find_one(
            {
                "_id": result['geoname_id']
            },
            {
                'geoname_id': 0,
                'continent_code': 0,
                'locale_code': 0,
                'metro_code': 0,
                'subdivision_2_name': 0,
                '_id': 0
            })
        if geo:
            print('Found GEO infos for {} in DB'.format(ip))
            for k, v in geo.iteritems():
                result[k] = v.encode('utf-8', 'ignore')


        # ASN data
        asns = db.asns
        asn = asns.find_one(
        {
            'start': { '$lte': ip_to_long },
            'end': { '$gte': ip_to_long }
        })
        if asn:
            logging.debug('Found ASN infos for {} in DB'.format(ip))
            result['asn_name'] = str(asn['name'])
            result['asn_number'] = str(asn['number'])

        del result['geoname_id']
        return dumps(result)

    else:
        logging.debug('{} NOT found in DB'.format(ip))
        result = app.notfound()


class req_ip:
    def GET(self):
        user_ip = web.ctx.ip

        if web.net.validipaddr(user_ip):
            logging.debug('Request user IP: {}'.format(user_ip))
            res = search_in_db(user_ip)

            web.header('Content-Type', 'application/json')
            web.header('Access-Control-Allow-Origin', '*')
            return res

        else:
            return app.notfound()

class find_ip:
    def GET(self, req):
        logging.debug('Search for IP: {}'.format(req))

        if web.net.validipaddr(req):
            res = search_in_db(req)

            web.header('Content-Type', 'application/json')
            web.header('Access-Control-Allow-Origin', '*')
            return res

        else:
            is_fqdn = re.match(r'^([a-zA-z0-9-]{,63}\.){1,2}([a-z]){2,5}$', req)

            if is_fqdn is not None:
                try:
                    h = socket.gethostbyname(req)
                    res = search_in_db(h)

                    web.header('Content-Type', 'application/json')
                    web.header('Access-Control-Allow-Origin', '*')
                    return res
                except socket.gaierror:
                    app.notfound()

            else:
                app.notfound()



application = app.wsgifunc()
