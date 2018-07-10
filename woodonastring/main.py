#!/usr/bin/env python


from pygtail import Pygtail
from datetime import datetime
from elasticsearch import Elasticsearch
import hashlib
import influxdb
import json
import os
import pathlib
import pprint
import time


def log(msg):
    ts = time.time()
    st = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    me = "woodonastring"
    print("{}: {} {}".format(st, me, msg))


def FileExists(filename):
    f = pathlib.Path(filename)
    if f.is_file():
        return True
    else:
        return False


def predicablehash(input):
    """
    returns a predicable hash for elastic id:{} field
    """

    foo = str(input)
    hash_object = hashlib.md5(foo.encode())
    return(hash_object.hexdigest())


def elastic_write(index, body):
    """
    index data into elastic
     - this function generates the id={} field based in a hash of the input
     - input "index" is used for standard ELK format.. EG: myprefix-YYYY-MM-DD
    """
    id = predicablehash(body)

    # TODO: assemble this from timestamp field (in the data itself)
    ts = time.time()
    timeYear = datetime.fromtimestamp(ts).strftime('%Y')
    timeMonth = datetime.fromtimestamp(ts).strftime('%m')
    timeDay = datetime.fromtimestamp(ts).strftime('%d')

    indexName = "{}-{}.{}.{}".format(
            index,
            timeYear,
            timeMonth,
            timeDay)
    es.index(index=indexName, doc_type='post', id=id, body=body)


# yaml pretty printer for debug
def pp(data):
    foo = pprint.PrettyPrinter(indent=4)
    foo.pprint(data)


# take raw traefik log entry and extract what we want
def transmogrify_elastic(input):
    BackendAddr = str(input['BackendAddr'])
    BackendName = input['BackendName']
    Duration = input['Duration']
    OriginStatus = input['OriginStatus']
    Overhead = input['Overhead']
    RequestAddr = input['RequestAddr']
    RequestMethod = input['RequestMethod']
    RequestPath = input['RequestPath']
    time = input['time']
    result = {
            "timestamp": time,
            "source": "traefik",
            "BackendName": BackendName,
            "BackendAddr": BackendAddr,
            "RequestAddr": RequestAddr,
            "RequestMethod": RequestMethod,
            "RequestPath": RequestPath,
            "OverHead": Overhead,
            "Duration": Duration,
            "OriginStatus": OriginStatus
        }

    return(result)


# take raw traefik log entry and extract what we want
def transmogrify_influx(input):
    BackendAddr = str(input['BackendAddr'])
    BackendName = input['BackendName']
    Duration = input['Duration']
    OriginStatus = input['OriginStatus']
    Overhead = input['Overhead']
    RequestAddr = input['RequestAddr']
    RequestMethod = input['RequestMethod']
    RequestPath = input['RequestPath']
    time = input['time']
    result = [
        {
            "measurement": "http",
            "tags": {
                "backend_name": BackendName,
                "backend_ip": BackendAddr,
                "client_ip": RequestAddr,
                "method": RequestMethod,
                "path": RequestPath
            },
            "time": time,
            "fields": {
                "OverHead": Overhead,
                "Duration": Duration,
                "Status": OriginStatus
            }
        }
    ]
    return(result)


if __name__ == '__main__':

    logFile = os.getenv("LOGFILE", default="../logs/access.json")
    posFile = os.getenv("POSFILE", default="pos.txt")

    influxdbEnabled = os.getenv("INFLUXDB_ENABLED", default=False)
    influxdbDataBase = os.getenv("INFLUXDB_DATABASE", default="traefik")
    influxdbHost = os.getenv("INFLUXDB_HOST", default="influxdb")
    influxdbPass = os.getenv("INFLUXDB_PASS", default="root")
    influxdbPort = os.getenv("INFLUXDB_PORT", default="8086")
    influxdbUser = os.getenv("INFLUXDB_USER", default="root")

    elasticEnabled = os.getenv("ELASTIC_ENABLED", default=True)
    elasticHost = os.getenv("ELASTIC_HOST", default="elastic")
    elasticPort = os.getenv("ELASTIC_PORT", default="9200")
    elasticPrefix = os.getenv("ELASTIC_PREFIX", default="logprefix")

    while not FileExists(logFile):
        log("failed to find file: {} .... sleeping 10s".format(logFile))
        time.sleep(10)
    else:
        log("streaming file: {}".format(logFile))
        # exit(1)

    if influxdbEnabled:
        influxclient = influxdb.InfluxDBClient(
                host=influxdbHost,
                port=influxdbPort,
                username=influxdbUser,
                password=influxdbPass,
                database=influxdbDataBase
                )
        influxclient.create_database(influxdbDataBase)

    if elasticEnabled:
        try:
            es = Elasticsearch([{'host': elasticHost, 'port': elasticPort}])
            log("connected to elastic")

        except Exception as ex:
            log("Error: {}".format(ex))

    linesProcessed = 0
    while True:
        buffer = {}
        for line in Pygtail(
                logFile,
                offset_file=posFile,
                every_n=1):
            sample = json.loads(line)

            if influxdbEnabled:
                payload = transmogrify_influx(sample)
                influxclient.write_points(payload)
                linesProcessed = linesProcessed + 1
                if linesProcessed % 100 == 0:
                    log("processed {} lines to influxdb {}/{}".format(
                        linesProcessed, influxdbHost, influxdbDataBase))

            if elasticEnabled:
                payload = transmogrify_elastic(sample)
                elastic_write(elasticPrefix, payload)
                linesProcessed = linesProcessed + 1
                if linesProcessed % 100 == 0:
                    log("processed {} lines to elk prefix '{}'".format(linesProcessed, elasticPrefix))

            if not influxdbEnabled and not elasticEnabled:
                log("not configured for any backend")

            # if linesProcessed % 100 == 0:
            #     log("processed {} lines".format(linesProcessed))
            #     timeLastLog = datetime.now()

    time.sleep(5)

