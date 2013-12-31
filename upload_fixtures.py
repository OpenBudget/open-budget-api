from gevent import monkey; monkey.patch_socket()
import gevent
from gevent.pool import Pool
import json
import urllib2
import sys

def do_write(data,i,kind):
    u = urllib2.urlopen('http://localhost:8080/api/update/%s' % kind, data).read()
    print u,i

if __name__=="__main__":
    pool = Pool(4)
    lines = {'bl':[],'cl':[]}
    i = 0
    for line in file('data/fixtures/fixtures.json'):
        line = json.loads(line)
        kind = line['fixture-type']
        del line['fixture-type']
        line = json.dumps(line)
        lines[kind].append(line.strip())
        if len(lines[kind]) == 100:
            pool.spawn(do_write, "\n".join(lines),i,kind)
            lines[kind] = []
        i+=1
    for kind, pending in lines.iteritems():
        if len(pending)>0:
            do_write("\n".join(lines),i,kind)
    pool.join()
