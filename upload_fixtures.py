import json
import urllib2
import sys

def do_write(data,i,kind):
    try:
        u = urllib2.urlopen('http://localhost:8080/api/update/%s' % kind, data).read()
        print u,i
    except Exception,e:
        print "Failed to upload batch %d: %s" % (i,e)
        print data

if __name__=="__main__":
    lines = {'bl':[],'cl':[]}
    i = 0
    for line in urllib2.urlopen("https://raw.github.com/OpenBudget/open-budget-data/master/fixtures/fixtures.json#"):
        line = json.loads(line)
        kind = line['fixture-type']
        del line['fixture-type']
        line = json.dumps(line)
        lines[kind].append(line.strip())
        if len(lines[kind]) == 100:
            do_write("\n".join(lines[kind]),i,kind)
            lines[kind] = []
        i+=1
    for kind, pending in lines.iteritems():
        if len(pending)>0:
            do_write("\n".join(lines[kind]),i,kind)
