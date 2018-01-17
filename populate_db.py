# -*- coding: utf-8 -*-

from pymongo import MongoClient
import zipfile
import csv
import urllib
import os
import shutil
from datetime import datetime
import netaddr
import sys
import logging
from bson.json_util import dumps
import argparse

### Save geoip data from maxmind into a mongo database ###

# Data config
csv_dir = './csv'
db_name = 'geoip'
client = MongoClient('mongodb://localhost:27017/')
db = client.geoip

csvs = {}
csvs['GeoLite2-City'] = 'http://geolite.maxmind.com/download/geoip/database/GeoLite2-City-CSV.zip'
csvs['GeoIPASNum2v6'] = 'http://download.maxmind.com/download/geoip/database/asnum/GeoIPASNum2v6.zip'
csvs['GeoIPASNum2'] = 'http://download.maxmind.com/download/geoip/database/asnum/GeoIPASNum2.zip'


# Logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s :: %(levelname)s :: %(message)s')


def countLine(filename):
    # Python 2: OK
    f = open(filename)
    lines = 0
    buf_size = 1024 * 1024
    read_f = f.read # loop optimization

    buf = read_f(buf_size)
    while buf:
        lines += buf.count('\n')
        buf = read_f(buf_size)

    return lines
    # TODO
    # Adapt for both python 2.7 and 3.6
    # Pyton 3: OK
    # f = open(filename, 'rb')
    # bufgen = takewhile(lambda x: x, (f.raw.read(1024*1024) for _ in repeat(None)))
    # return sum( buf.count(b'\n') for buf in bufgen if buf )


def cleandir(directory):
    try:
        for root, dirs, files in os.walk(directory):
            for file in files:
                filename, file_extension = os.path.splitext(file)

                if file == 'GeoLite2-City-Locations-en.csv':
                    shutil.move(os.path.join(root, file), os.path.join(csv_dir, file))
                elif file.find('GeoLite2-City-Blocks') != -1:
                    shutil.move(os.path.join(root, file), os.path.join(csv_dir, file))
                elif file_extension == '.zip':
                    os.remove(os.path.join(root, file))

        return True
    except Exception as e:
        logging.error('Cleaning directory: {}'.format(e))
        return False


def unzipFile(filename):
    with zipfile.ZipFile(filename,"r") as zip_ref:
        zip_ref.extractall(csv_dir)


def processGeoLocation(data):
    data['_id'] = data['geoname_id']

    try:
        geos = db.geos
        geo_id = geos.insert_one(data).inserted_id

    except Exception as e:
        logging.error('saving in GeoLocation collection: {}'.format(e))
        pass


def processAsn(data):
    asn_string = data[2].split();
    asn_num = asn_string[0];
    asn_string.remove(asn_num)
    asn_name = ' '.join(str(x) for x in asn_string)
    asn_name = asn_name.decode("iso-8859-1").encode("utf-8")
    asn_id = str(data[0]) + str(data[1])


    data_asn = {}
    data_asn['_id'] = asn_id
    data_asn['name'] = asn_name
    data_asn['number'] = asn_num
    data_asn['start'] = int(data[0])
    data_asn['end'] = int(data[1])

    try:
        asns = db.asns
        asn_id = asns.insert_one(data_asn).inserted_id

    except Exception as e:
        logging.error('saving in ASNS collection: {}'.format(e))
        pass


def processIPv4(data):

    data['start'] = netaddr.IPNetwork(data['network']).first
    data['end'] = netaddr.IPNetwork(data['network']).last

    try:
        ips = db.ips
        ip_id = ips.insert_one(data).inserted_id

    except Exception as e:
        logging.error('saving in IPS collection: {}'.format(e))
        pass


def log_process(file, inserted_line, total_line):
    # Log every 1500 lines
    if (inserted_line % 1500) == 0:
        logging.info('{}: {} done over {}'.format(file, inserted_line, total_line))


def processCsvs(csv_dir):
    files = ['GeoIPASNum2.csv', 'GeoLite2-City-Locations-en.csv', 'GeoLite2-City-Blocks-IPv4.csv']
    for file in files:

        if file == 'GeoIPASNum2.csv':
            logging.info('Processing {} file...'.format(file))
            total_line = countLine(os.path.join(csv_dir, file))
            inserted_line = 0
            with open(os.path.join(csv_dir, file), "rb") as csvfile:

                reader = csv.reader(csvfile)
                for row in reader:
                    inserted_line += 1
                    log_process(file, inserted_line, total_line)
                    processAsn(row)

        elif file == 'GeoLite2-City-Locations-en.csv':
            logging.info('Processing {} file...'.format(file))
            total_line = countLine(os.path.join(csv_dir, file))
            inserted_line = 0
            with open(os.path.join(csv_dir, file), "rb") as csvfile:

                reader = csv.DictReader(csvfile)
                for row in reader:
                    inserted_line += 1
                    log_process(file, inserted_line, total_line)
                    processGeoLocation(row)

        elif file == 'GeoLite2-City-Blocks-IPv4.csv':
            logging.info('Processing {} file...'.format(file))
            total_line = countLine(os.path.join(csv_dir, file))
            inserted_line = 0

            # Exit if ASN and GEOS collections are empty
            if db.asns.count() == 0:
                logging.error('Canceled... ASN Collection is empty !')
                sys.exit(1)

            elif db.geos.count () == 0:
                logging.error('Canceled... Geos Collection is empty !')
                sys.exit(1)

            with open(os.path.join(csv_dir, file), "rb") as csvfile:

                reader = csv.DictReader(csvfile)
                for row in reader:
                    inserted_line += 1
                    log_process(file, inserted_line, total_line)
                    processIPv4(row)

        else:
            logging.warning('Unknown file {}: skipped'.format(file))

def processFiles(csvs):

    for filename, url in csvs.iteritems():
        zip_file = os.path.join(csv_dir, filename + '.zip')

        # download files
        logging.info('downloading {}...'.format(zip_file))
        download = urllib.URLopener()

        download.retrieve(url, zip_file)

        # Unzi files
        with zipfile.ZipFile(zip_file,"r") as zip_ref:
            zip_ref.extractall(csv_dir)

    clean = cleandir(csv_dir)

    if clean:
        processCsvs(csv_dir)


def update(csv_dir):
    # Update if csv_dir is older than 7 days
    # Last update check from csv_dir last modified date
    d = os.stat(csv_dir)
    last_modified = datetime.fromtimestamp(d.st_mtime)
    delta = datetime.now() - last_modified

    if delta.days >= 7:
        # Backup db
        backupCsvs(csv_dir)
    else:
        os.exit('Files are less than 7 days old. Skipping...')


def backupCsvs(csv_dir):
    if os.path.exists(csv_dir):
        now = datetime.now()
        now = now.strftime("%Y-%m-%d_")
        backup = now + 'csv'

        shutil.move(csv_dir, backup)
        os.makedirs(csv_dir)
    else:
        os.makedirs(csv_dir)


def dropDB(db_name):
    try:
        client.drop_database(db_name)
        return True
    except Exception as e:
        logging.error('Drop database [ FAILED ]: {}'.format(e))
        return False


def copyDB(db_name):

    now = datetime.now()
    bck_db_name = now.strftime("%Y-%m-%d_{}".format(db_name))

    try:
        client.admin.command('copydb', fromdb=db_name, todb=bck_db_name)
        logging.debug('Copy database {} [ OK ]'.format(db_name))
        return True
    except Exception as e:
        logging.error('Copy database {} [ FAILED ]'.format(db_name))
        return False


def main():

    backupCsvs(csv_dir)

    # download and unzip csv files
    processFiles(csvs)

    ## TODO:
    # Locales
    # IPv6

if __name__ == '__main__':

            parser = argparse.ArgumentParser(description='Populate Mongodb DB from Maxmind GeoIP CSVs')
            parser.add_argument('-n','--new', action='store_true', default=False, help='Create GeoIP database')
            parser.add_argument('-u','--update', action='store_true', default=False, help='Backup or drop existing database and create a new one')
            parser.add_argument('-nb','--no-backup', default=False, help='Update without backup of existing database', action='store_true')


            args = parser.parse_args()

            if args.new:
                db_exists = client.database_names()
                if db_name in db_exists:
                    os.exit('Database {} exists. Please use --update'.format(db_name))
                else:
                    processFiles(csvs)

            elif args.update:
                if args.no_backup:
                    dropDB(db_name)
                else:
                    cp = copyDB(db_name)
                    if cp:
                        dropDB(db_name)

                update(csv_dir)
                processFiles(csvs)

            else :
                parser.print_help()
