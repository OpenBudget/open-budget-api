#! /usr/bin/python
import json
import urllib2
import sys
import uuid
import time
import hashlib
import hmac
import requests


def sign(key, path, expires):
    if not key:
        return None

    h = hmac.new(str(key), msg=path, digestmod=hashlib.sha1)
    h.update(str(expires))

    return h.hexdigest()

def get_query(redash_url, query_id, secret_api_key):
    path = '/api/queries/{}/results.json'.format(query_id)
    expires = time.time()+900 # expires must be <= 3600 seconds from now
    signature = sign(secret_api_key, path, expires)
    full_path = "{0}{1}?signature={2}&expires={3}".format(redash_url, path,
                                                          signature, expires)

    return requests.get(full_path).json()


API_KEY = "d262c9f9-a77e-4adb-b73a-ce818bb05b8b"

def do_write(data,i,kind):
    try:
        u = urllib2.urlopen('http://localhost:8080/api/update/%s?apikey=%s' % (kind,API_KEY), data).read()
        print u,i
    except Exception,e:
        print "Failed to upload batch %d: %s" % (i,e)

if __name__=="__main__":
    queryDescriptorList = {
        'bl': {'queryId' : 65, "secret_api_key": "e05145295f37859eac36b35aa38d372ea4d0f23b"},
        'cl': {'queryId' : 66, "secret_api_key": "972b372701c210ba0aa8675dd0d381448530a76b"},
        'sl': {'queryId' : 67, "secret_api_key": "97ccab8c67e9151fc1b65406209d4899ba62b7ef"},
        'mr': {'queryId' : 68, "secret_api_key": "7216dd069d3b04780ec1ea19c12cc509adda7560"},
        'en': {'queryId' : 75, "secret_api_key": "f5eaea5824a49f73d20f57d20b775c4e54b148e4"}
    }

    aggregation = 100
    for kind, queryDescriptor in queryDescriptorList.iteritems():
        print "Processing query %d" % queryDescriptor['queryId']
        queryJSON = get_query("http://data.obudget.org", queryDescriptor['queryId'], queryDescriptor['secret_api_key'])
        print queryJSON
        budgetData = queryJSON['query_result']['data']['rows']
        lines = []
        i = 0
        for line in budgetData:
            lines.append(json.dumps(line))
            i = i + 1
            if (i % aggregation == 0 and len(lines) > 0):
                do_write("\n".join(lines),i,kind)
                lines = []
