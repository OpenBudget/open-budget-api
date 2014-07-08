# encoding: utf8

import os
import webapp2
import json
import jinja2
import datetime
import re
import logging
import urllib
import csv
import StringIO

from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.api import users

from models import BudgetLine, SupportLine, ChangeLine, SearchHelper, PreCommitteePage, ChangeExplanation, SystemProperty, ChangeGroup, CompanyRecord, NGORecord
from secret import ALLOWED_EMAILS, UPLOAD_KEY

INFLATION = {1992: 2.338071159424868,
 1993: 2.1016785142253185,
 1994: 1.8362890269054741,
 1995: 1.698638328862775,
 1996: 1.5360153664058611,
 1997: 1.4356877762122495,
 1998: 1.3217305991625745,
 1999: 1.3042057718241757,
 2000: 1.3042057718241757,
 2001: 1.2860800081392196,
 2002: 1.2076314957018655,
 2003: 1.2308469660644752,
 2004: 1.2161648953888384,
 2005: 1.1878270593983091,
 2006: 1.1889814138002117,
 2007: 1.1499242230869946,
 2008: 1.1077747422214268,
 2009: 1.0660427753379829,
 2010: 1.0384046275616676,
 2011: 1.0163461588107117,
 2012: 1.0,
 2013: 1.0/1.017,
 2014: 1.0/(1.017*1.023),
}

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class Update(webapp2.RequestHandler):

    def post(self,what):
        self.response.headers['Content-Type'] = 'text/plain'

        key = self.request.get("apikey")
        user = users.get_current_user()
        if (user is None or user.email() not in ALLOWED_EMAILS) and key != UPLOAD_KEY:
            self.abort(403)

        #body = urllib.unquote_plus(self.request.body)
        body = self.request.body
        body = body.strip()
        to_update = body.split('\n')
        try:
            to_update = [ json.loads(x) for x in to_update if x.strip() != '' ]
        except Exception,e:
            print body
            raise
        to_put = []
        to_delete = []
        for item in to_update:
            dbitem = None
            if what == "sp":
                dbitem = SystemProperty.query(SystemProperty.key==item['key']).fetch(1)
                if len(dbitem) == 0:
                    self.response.write("No system property for key=%(key)s" % item)
                    dbitem = SystemProperty()
                else:
                    for x in dbitem[1:]:
                        to_delete.append(x)
                    dbitem = dbitem[0]

            if what == "bl":
                dbitem = BudgetLine.query(BudgetLine.year==item['year'],BudgetLine.code==item['code']).fetch(1)
                if len(dbitem) == 0:
                    self.response.write("No budget item for year=%d, code=%s" % (item['year'],item['code']))
                    dbitem = BudgetLine()
                else:
                    for x in dbitem[1:]:
                        to_delete.append(x)
                    dbitem = dbitem[0]
                code = item['code']
                prefixes = [ code[:l] for l in range(2,len(code),2) ]
                prefixes.append(code)
                #self.response.write("%s==>%s\n" % (code,prefixes))
                item["prefixes"] = prefixes
                item["depth"] = len(code)/2 - 1

            if what == "cl":
                if item['year'] is None or item['leading_item'] is None or item['req_code'] is None or item['budget_code'] is None:
                    self.abort(400)
                dbitem = ChangeLine.query(ChangeLine.year==item['year'],
                                          ChangeLine.leading_item==item['leading_item'],
                                          ChangeLine.req_code==item['req_code'],
                                          ChangeLine.budget_code==item['budget_code']).fetch(1)
                if len(dbitem) == 0:
                    self.response.write("No change item for year=%(year)d, leading_item=%(leading_item)d, req_code=%(req_code)d, code=%(budget_code)s" % item)
                    dbitem = ChangeLine()
                else:
                    for x in dbitem[1:]:
                        to_delete.append(x)
                    dbitem = dbitem[0]
                code = item['budget_code']
                prefixes = [ code[:l] for l in range(2,len(code),2) ]
                prefixes.append(code)
                #self.response.write(code+"==>"+repr(prefixes)+"\n")
                item["prefixes"] = prefixes
                if item.get('date') is not None and item['date'] != "":
                    try:
                        item['date'] = datetime.datetime.strptime(item['date'],'%d/%m/%Y')
                    except:
                        item['date'] = datetime.datetime.fromtimestamp(item['date']/1000.0+86400)
                    item['date'] = item['date'].date()

            if what == "cg":
                if item['year'] is None or item['group_id'] is None:
                    self.abort(400)
                dbitem = ChangeGroup.query(ChangeGroup.year==item['year'],
                                           ChangeGroup.group_id==item['group_id']).fetch(1)
                if len(dbitem) == 0:
                    self.response.write("No change group for year=%(year)d, group_id=%(group_id)s" % item)
                    dbitem = ChangeGroup()
                else:
                    for x in dbitem[1:]:
                        to_delete.append(x)
                    dbitem = dbitem[0]
                if item.get('date') is not None and item['date'] != "":
                    item['date'] = datetime.datetime.strptime(item['date'],'%d/%m/%Y')
                    item['date'] = item['date'].date()

            if what == "ex":
                if item['year'] is None or item['leading_item'] is None or item['req_code'] is None:
                    self.abort(400)
                dbitem = ChangeExplanation.query(ChangeLine.year==item['year'],
                                                 ChangeLine.leading_item==item['leading_item'],
                                                 ChangeLine.req_code==item['req_code']).fetch(1)
                if len(dbitem) == 0:
                    self.response.write("No change explanation for year=%(year)d, leading_item=%(leading_item)d, req_code=%(req_code)d" % item)
                    dbitem = ChangeExplanation()
                else:
                    for x in dbitem[1:]:
                        to_delete.append(x)
                    dbitem = dbitem[0]

            if what == "sl":
                if item["year"] is None or item["code"] is None or item["recipient"] is None or item["kind"] is None or item["title"] is None:
                    self.abort(400)
                dbitem = SupportLine.query(SupportLine.year==item["year"],
                                           SupportLine.code==item["code"],
                                           SupportLine.recipient==item["recipient"],
                                           SupportLine.kind==item["kind"],
                                           SupportLine.title==item["title"]).fetch(100)
                if len(dbitem) == 0:
                    self.response.write("No support item for year=%(year)s, code=%(code)s, recipient=%(recipient)s, kind=%(kind)s, title=%(title)s" % item)
                    dbitem = SupportLine()
                else:
                    for x in dbitem[1:]:
                        to_delete.append(x)
                    dbitem = dbitem[0]
                code = item['code']
                prefixes = [ code[:l] for l in range(2,len(code),2) ]
                prefixes.append(code)
                item["prefixes"] = prefixes

            if what == "sh":
                dbitem = SearchHelper.query(SearchHelper.kind==item['kind'],SearchHelper.value==item['value'],SearchHelper.year==max(item['year'])).fetch(1000,batch_size=1000)
                if len(dbitem) == 0:
                    self.response.write("No searchhelper for kind=%(kind)s, value=%(value)s, year=%(year)r\n" % item)
                    dbitem = SearchHelper()
                else:
                    for x in dbitem[1:]:
                        to_delete.append(x)
                    dbitem = dbitem[0]
                item["prefix"] = None

            if what == "pcp":
                dbitem = PreCommitteePage.query(PreCommitteePage.pdf==blobstore.BlobKey(item['pdf']), PreCommitteePage.page==blobstore.BlobKey(item['page'])).fetch(100)
                if len(dbitem) == 0:
                    self.response.write("No PreCommitteePage for pdf=%(pdf)s, page=%(page)s\n" % item)
                    dbitem = PreCommitteePage()
                else:
                    for x in dbitem[1:]:
                        to_delete.append(x)
                    dbitem = dbitem[0]
                del item["pdf"]
                del item["page"]

            if what == "cr":
                dbitem = CompanyRecord.query(CompanyRecord.registration_id==item['registration_id']).fetch(1)
                if len(dbitem) == 0:
                    self.response.write("No company record for registration_id=%(registration_id)s" % item)
                    dbitem = CompanyRecord()
                else:
                    for x in dbitem[1:]:
                        to_delete.append(x)
                    dbitem = dbitem[0]

            if what == "ngo":
                dbitem = NGORecord.query(NGORecord.amuta_id==item['amuta_id']).fetch(1)
                if len(dbitem) == 0:
                    self.response.write("No NGO record for amuta_id=%(amuta_id)s" % item)
                    dbitem = NGORecord()
                else:
                    for x in dbitem[1:]:
                        to_delete.append(x)
                    dbitem = dbitem[0]

            def mysetattr(i,k,v):
                orig_v = i.__getattribute__(k)
                if type(orig_v) == list and type(v) == list:
                    orig_v.sort()
                    v.sort()
                    if json.dumps(orig_v) != json.dumps(v):
                        i.__setattr__(k,v)
                        self.response.write("%s: %s: %r != %r\n" % (i.key, k,orig_v,v))
                        return True
                else:
                    if orig_v != v:
                        i.__setattr__(k,v)
                        self.response.write("%s: %s: %r != %r\n" % (i.key, k,orig_v,v))
                        return True
                return False

            if dbitem is not None:
                dirty = False
                for k,v in item.iteritems():
                    dirty = mysetattr(dbitem,k,v) or dirty
                if dirty:
                    to_put.append(dbitem)

        if len(to_put) > 0:
            ndb.put_multi(to_put)
        if len(to_delete) > 0:
            ndb.delete_multi([x.key for x in to_delete])
        self.response.write("OK %d/%d-%d\n" % (len(to_put),len(to_update),len(to_delete)))

class CustomJSONEncoder(json.JSONEncoder):
    def default(self,o):
        if type(o) == datetime.date:
            return o.strftime("%d/%m/%Y")
        elif type(o) == datetime.datetime:
            return o.isoformat()
        return json.JSONEncoder.default(self, o)

def HTMLEncode(data, fields):
    header = u"<thead>%s</thead>" % "".join( u"<th>%s</th>" % f for f in fields )
    body = "".join( u"<tr>%s</tr>" % "".join( u"<td>%s</td>" % row[f] for f in fields ) for row in data )
    table = "<table>%s<tbody>%s</tbody></table>" % (header,body)
    return table.encode('utf8')

def CSVEncode(data,fields):
    output = StringIO.StringIO()
    writer = csv.writer(output)
    writer.writerow(fields)
    for row in data:
        writer.writerow([unicode(row[f]).encode('utf8') for f in fields])
    return output.getvalue()

class GenericApi(webapp2.RequestHandler):

    def do_paging(self):
        return True

    def get(self,*args,**kw):

        self.single = False
        self.first = self.request.get('first')
        if self.first is not None and self.first != '':
            self.first = int(self.first)
        else:
            self.first = 0
        self.limit = self.request.get('limit')
        if self.limit is not None and self.limit != '':
            self.limit = int(self.limit)
        else:
            self.limit = 100
        self.output_format = self.request.get('o')
        if self.output_format not in ['html','json','csv']:
            self.output_format = 'json'

        key = self.key(*args,**kw)+"//%s/%s/%s" % (self.first,self.limit,self.output_format)
        data = memcache.get(key)
        if data is not None:
            ret = data.decode("zip")
        else:
            query = self.get_query(*args,**kw)
            if self.do_paging():
                ret = [ x.to_dict() for x in query.fetch(batch_size=self.first+self.limit,limit=self.limit,offset=self.first) ]
            else:
                ret = [ x.to_dict() for x in query.fetch(batch_size=self.limit) ]
            if self.output_format == 'json':
                self.response.headers['Content-Type'] = 'application/json'
                if self.single and len(ret)>0:
                    ret = ret[0]
                ret = CustomJSONEncoder().encode(ret)
            elif self.output_format == 'html':
                self.response.headers['Content-Type'] = 'text/html'
                fields = []
                if len(ret)>0:
                    fields = ret[0].keys()
                ret = HTMLEncode(ret, fields)
            elif self.output_format == 'csv':
                self.response.headers['Content-Type'] = 'text/csv'
                fields = []
                if len(ret)>0:
                    fields = ret[0].keys()
                ret = CSVEncode(ret, fields)
            memcache.add(key, ret.encode("zip"), 30)

        if self.output_format == 'json':
            callback = self.request.get('callback')
            if callback is not None and callback != "":
                ret = "%s(%s);" % ( callback, ret )

        self.response.write(ret)

class BudgetApi(GenericApi):

    def key(self,code,year=None,kind=None):
        return "BudgetApi:%s/%s/%s" % (code,year,kind)

    def get_query(self,code,year=None,kind=None):
        if year != None:
            year = int(year)
            if kind is None:
                lines = BudgetLine.query(BudgetLine.code==code,BudgetLine.year==year)
                self.single = True
            elif kind == "kids":
                lines = BudgetLine.query(code_starts_with(BudgetLine,code),BudgetLine.depth==len(code)/2,BudgetLine.year==year)
            elif kind == "parents":
                parent_codes = [ code[:x] for x in range(2,len(code)+1,2) ]
                lines = BudgetLine.query(BudgetLine.code.IN(parent_codes),BudgetLine.year==year)
        else:
            lines = BudgetLine.query(BudgetLine.code==code).order(BudgetLine.year)
        return lines

class ChangesApi(GenericApi):

    def key(self,*args,**kw):
        return "ChangesApi:%s" % "/".join(args)

    def get_query(self,*args,**kw):
        code = leading_item = req_code = year = None
        if len(args) == 1:
            code = args[0]
        elif len(args) == 2:
            code, year = args
        elif len(args) == 3:
            leading_item, req_code, year = args
        if year is not None:
            year = int(year)
            if code is not None:
                lines = ChangeLine.query(ChangeLine.prefixes==code,ChangeLine.year==year).order(-ChangeLine.year,-ChangeLine.date)
            else:
                leading_item = int(leading_item)
                req_code = int(req_code)
                lines = ChangeLine.query(ChangeLine.leading_item==leading_item,ChangeLine.req_code==req_code,ChangeLine.year==year).order(-ChangeLine.year,-ChangeLine.date)
        else:
            lines = ChangeLine.query(ChangeLine.prefixes==code).order(-ChangeLine.year,-ChangeLine.date)
        return lines

class ChangeGroupApi(GenericApi):

    def key(self,*args,**kw):
        return "ChangeGroupApi:%s" % "/".join(args)

    def get_query(self,*args,**kw):
        code = leading_item = req_code = year = None
        if len(args) == 1:
            code = args[0]
        elif len(args) == 2:
            code, year = args
        if '-' in code:
            transfer_id = code
            self.single = True
            code = None
        if year is not None:
            year = int(year)
            if code is not None:
                lines = ChangeGroup.query(ChangeGroup.prefixes==code,ChangeGroup.year==year).order(-ChangeGroup.date)
            else:
                lines = ChangeGroup.query(ChangeGroup.transfer_ids==transfer_id,ChangeGroup.year==year).order(-ChangeGroup.date)
        else:
            lines = ChangeGroup.query(ChangeGroup.prefixes==code).order(-ChangeGroup.date)
        return lines

class ChangesPendingApi(GenericApi):

    def key(self,*args,**kw):
        return "ChangesPendingApi:%s" % "/".join(args)

    def get_query(self,*args,**kw):
        kind = args[0]
        lines = None
        if kind == 'all':
            lines = ChangeLine.query(ChangeLine.date_type==10).order(-ChangeLine.date)
        if kind == 'committee':
            lines = ChangeLine.query(ChangeLine.date_type==10,ChangeLine.change_type_id==2).order(-ChangeLine.date)
        return lines

class ChangeGroupsPendingApi(GenericApi):

    def key(self,*args,**kw):
        return "ChangeGroupsPendingApi:%s" % "/".join(args)

    def get_query(self,*args,**kw):
        lines = ChangeGroup.query(ChangeGroup.pending==True).order(-ChangeGroup.date)
        return lines


class ChangeExplApi(GenericApi):

    def key(self,*args,**kw):
        return "ChangeExplApi:%s" % "/".join(args)

    def get_query(self,*args,**kw):
        leading_item, req_code, year = args
        year = int(year)
        leading_item = int(leading_item)
        req_code = int(req_code)
        expl = ChangeExplanation.query(ChangeExplanation.leading_item==leading_item,ChangeExplanation.req_code==req_code,ChangeExplanation.year==year)
        self.single = True
        return expl

class SupportsApi(GenericApi):

    def key(self,*args):
        if args[0] == 'recipient':
            return "SupportsApi:%s" % args[1].encode('hex')
        else:
            return "SupportsApi:%s" % args[0]

    def get_query(self,*args):
        if args[0] == 'recipient':
            recipient = args[1].decode('utf8')
            recipients = list(set([ recipient, recipient[:35] ]))
            lines = SupportLine.query(SupportLine.recipient.IN(recipients)).order(SupportLine.code,SupportLine.kind,SupportLine.year)
        else:
            code = args[0]
            lines = SupportLine.query(SupportLine.prefixes==code).order(SupportLine.recipient,SupportLine.kind,SupportLine.year)
        return lines

class SystemPropertyApi(GenericApi):

    def key(self,key):
        return "SystemPropertyApi:%s" % key

    def get_query(self,key):
        lines = SystemProperty.query(SystemProperty.key==key)
        self.single = True
        return lines

class CompanyNGOApi(GenericApi):

    def key(self,kind,id):
        return "CompanyNGOApi:%s/%s" % (kind,id)

    def get_query(self,kind,id):
        self.single = True
        if kind == "company":
            lines = CompanyRecord.query(CompanyRecord.registration_id==id)
        elif kind == "ngo":
            lines = NGORecord.query(NGORecord.amuta_id==id)
        return lines

WORDS = re.compile(u'([א-ת0-9a-zA-Z]+)')

class SearchApi(GenericApi):

    def do_paging(self):
        return False

    def key(self,kind,year=None):
        queryString = self.request.get('q')
        return "SearchApi:%s/%s/%s" % (kind,year,queryString)

    def get_query(self,kind,year=None):

        queryString = self.request.get('q')
        parts = WORDS.findall(queryString)
        if kind == 'budget':
            codes = None
            token_condition = [ SearchHelper.tokens==part for part in parts ]
            token_condition = ndb.AND(*token_condition)
            if year is None:
                query = SearchHelper.query(token_condition, SearchHelper.kind=="BudgetLine").order(SearchHelper.priority)
            else:
                year = int(year)
                query = SearchHelper.query(token_condition, SearchHelper.kind=="BudgetLine", SearchHelper.year==year).order(SearchHelper.priority)
            #part_codes = set()
            part_codes = []
            for rec in query.fetch(self.limit,batch_size=self.limit):
                part_codes.append((rec.value,year if year is not None else max(rec.year)))

            #if codes is None:
            #    codes = part_codes
            #else:
            #    codes.intersection_update(part_codes)

            codes = list(part_codes)
            #codes.sort( key=lambda(x): "%08d/%s" % (len(x[0]),x[0]) )
            #codes = codes[self.first:self.first+self.limit]
            conditions = [ ndb.AND( BudgetLine.code==code, BudgetLine.year==year) for code,year in codes ]
            conditions.append( BudgetLine.code=="non-existent-code" )
            return BudgetLine.query( ndb.OR(*conditions) )

        return None

class PendingChangesRss(webapp2.RequestHandler):

    def get(self):
        self.response.headers['Content-Type'] = 'application/rss+xml'
        rss_template = JINJA_ENVIRONMENT.get_template('rss_template.xml')
        item_template = JINJA_ENVIRONMENT.get_template('webapp/email/email_item_template.jinja.html')
        feed_template = file('webapp/email/email_template.mustache.html').read().decode('utf8')
        rss_item_ids = SystemProperty.query(SystemProperty.key=='rss_items').fetch(1)[0]
        last_mod = rss_item_ids.last_modified
        rss_item_ids = rss_item_ids.value
        rss_title = SystemProperty.query(SystemProperty.key=='rss_title').fetch(1)[0].value
        rss_items = []
        for i in rss_item_ids:
            item = SystemProperty.query(SystemProperty.key=='rss_items[%s]' % i).fetch(1)[0]
            item = item.value
            item['baseurl']='http://the.open-budget.org.il/static/email/'
            item['pubdate']=last_mod.isoformat()
            rss_items.append(item)
        rss_items = [ { 'title': item['title'],
                        'description': item_template.render(item),
                        'link': "http://the.open-budget.org.il/stg/#transfer/%s/%s" % (item['group_id'],item['group'][0][0]),
                        'score': item['score'],
                        'pubdate': item['pubdate'] } for item in rss_items ]
        to_render = { 'title': rss_title,
                      'feed_template': feed_template,
                      'items': rss_items }
        out = rss_template.render(to_render)
        self.response.write(out)


class PdfStatusApi(webapp2.RequestHandler):

    def get(self,key):
        self.response.headers['Content-Type'] = 'application/json'
        pages = PreCommitteePage.query(PreCommitteePage.pdf==blobstore.BlobKey(key)).fetch(100)
        done = False
        pages = list(pages)
        for page in pages:
            if page.last == True:
                done = True
        if len(pages)==1 and pages[0].page is None:
            ret = 0
        else:
            ret = len(pages)
        ret = { 'numPages': ret,
                'done' :  done }
        self.response.write(json.dumps(ret))

class ReportAll(webapp2.RequestHandler):

    def get(self,year):
        year = int(year)
        all_items = BudgetLine.query(BudgetLine.depth==3,BudgetLine.year==year).order(BudgetLine.code)

        template_values = {
            'year': year,
            'items': all_items,
        }
        template = JINJA_ENVIRONMENT.get_template('all_for_report.html')
        self.response.write(template.render(template_values))

def prefix_starts_with(clz,prefix):
    next = prefix[:-1] + unichr(ord(prefix[-1])+1)
    return ndb.AND(clz.prefix>=prefix,clz.prefix<next)

def code_starts_with(clz,prefix):
    return ndb.AND(clz.code>=prefix,clz.code<prefix+'X')

class Report(webapp2.RequestHandler):

    def get(self,code,year):

        callback = self.request.get('callback')

        key = code+":"+year
        data = memcache.get(key)
        if data is not None:
            ret = data.decode("zip")
        else:
            year = int(year)

            ## actual record
            rec = BudgetLine.query(BudgetLine.code==code, BudgetLine.year==year).fetch(1)[0]
            rec_data = rec.to_dict()

            ### async queries
            parent_codes = [ prefix for prefix in rec.prefixes if prefix != code and prefix != "00" ]
            parent_query = BudgetLine.query(BudgetLine.code.IN(parent_codes),
                                            BudgetLine.year==year).fetch_async(batch_size=100)
            prefixes = [ prefix for prefix in rec.prefixes if prefix != "00" ]
            prefixes = [ (len(prefix)/2, prefix) for prefix in prefixes ]
            hierarchy_queries = [ (depth,
                                   BudgetLine.query(code_starts_with(BudgetLine,prefix),
                                                    BudgetLine.year==year,
                                                    BudgetLine.depth==depth).order(BudgetLine.code).fetch_async(batch_size=500))
                                  for depth, prefix in prefixes ]
            history_query = BudgetLine.query(BudgetLine.code==code).fetch_async(batch_size=500)
            support_query = SupportLine.query(SupportLine.prefixes==code).order(SupportLine.year).fetch_async(batch_size=500)
            changes_query = ChangeLine.query(ChangeLine.prefixes==code).order(-ChangeLine.year,-ChangeLine.date).fetch_async(batch_size=500)

            ## parents
            parents = [ record.to_dict() for record in parent_query.get_result() ]

            ## hierarchy
            by_depth = [ (depth,[ record.to_dict() for record in query.get_result() ]) for depth,query in hierarchy_queries ]
            by_depth = dict(by_depth)

            ## history over the years
            history_recs = dict([ (record.year,record) for record in history_query.get_result() ])
            history = []
            for y in range(year,1991,-1):
                rec = history_recs.get(y)
                inf = INFLATION[y] / INFLATION[2013]
                if rec is None:
                    break
                to_add = { 'year': rec.year, 'title': rec.title }
                if rec.net_allocated is not None: to_add['net_allocated'] = rec.net_allocated*inf,
                if rec.net_revised is not None: to_add['net_revised'] = rec.net_revised*inf,
                if rec.net_used is not None: to_add['net_used'] = rec.net_used*inf,
                if rec.gross_allocated is not None: to_add['gross_allocated'] = rec.gross_allocated*inf,
                if rec.gross_revised is not None: to_add['gross_revised'] = rec.gross_revised*inf,
                if rec.gross_used is not None: to_add['gross_used'] = rec.gross_used*inf,
                history.append(to_add)

            ## supports
            support_recs = [ record.to_dict() for record in support_query.get_result() ]
            supports = {}
            for support in support_recs:
                support_code = support['code']
                if support_code not in supports.keys():
                    supports[support_code] = {'code':support_code,
                                              'title':support['title'],
                                              'subject':support['subject'],
                                              'recipients':{}}
                recipient = supports[support_code]['recipients'].setdefault(support['recipient'],{})
                recipient.setdefault('sum',0)
                recipient.setdefault('count',0)
                recipient['sum'] += support['amount_used']*INFLATION[support['year']] / INFLATION[2013]
                recipient['count'] += 1

                l = recipient.setdefault('kinds',{}).setdefault(support['kind'],[])
                l.append({'year':support['year'],
                          'num_supported':support['num_supported'],
                          'amount_used':support['amount_used'],
                          'amount_allocated':support['amount_allocated']})

            ## changes
            changes = [ {'year':rec.year,
                         'date':None if rec.date is None else rec.date.strftime("%d/%m/%Y"),
                         'explanation': rec.explanation,
                         'req_title': rec.req_title,
                         'change_title': rec.change_title,
                         'change_type_name': rec.change_type_name,
                         'net_expense_diff': rec.net_expense_diff,
                         'gross_expense_diff': rec.gross_expense_diff,
                         'allocated_income_diff': rec.allocated_income_diff,
                         'commitment_limit_diff': rec.commitment_limit_diff,
                         'personnel_max_diff': rec.personnel_max_diff } for rec in changes_query.get_result() ]

            ret = { 'code'    : repr(code),
                    'rec'     : rec_data,
                    'parents' : parents,
                    'hierarchy' : by_depth,
                    'history' : history,
                    'supports': supports,
                    'changes' : changes }
            ret = json.dumps(ret)
            memcache.add(key, ret.encode("zip"), 7200)

        self.response.headers['Content-Type'] = 'application/json'
        if callback is not None and callback != "":
            ret = "%s(%s);" % ( callback, ret )
        self.response.write(ret)

api = webapp2.WSGIApplication([
    ('/api/budget/([0-9]+)', BudgetApi),
    ('/api/budget/([0-9]+)/([0-9]+)', BudgetApi),
    ('/api/budget/([0-9]+)/([0-9]+)/(kids)', BudgetApi),
    ('/api/budget/([0-9]+)/([0-9]+)/(parents)', BudgetApi),
    ('/api/changes/([0-9]+)', ChangesApi),
    ('/api/changes/pending/(all)', ChangesPendingApi),
    ('/api/changes/pending/(committee)', ChangesPendingApi),
    ('/api/changes/([0-9]+)/([0-9]+)', ChangesApi),
    ('/api/changes/([0-9][0-9])-([0-9][0-9][0-9])/([0-9]+)', ChangesApi),

    ('/api/changegroup/([0-9]+)', ChangeGroupApi),
    ('/api/changegroup/pending', ChangeGroupsPendingApi),
    ('/api/changegroup/([0-9]+)/([0-9]+)', ChangeGroupApi),
    ('/api/changegroup/([0-9][0-9]-[0-9][0-9][0-9])/([0-9]+)', ChangeGroupApi),

    ('/api/change_expl/([0-9][0-9])-([0-9][0-9][0-9])/([0-9]+)', ChangeExplApi),
    ('/api/supports/([0-9]+)', SupportsApi),
    ('/api/supports/(recipient)/(.+)', SupportsApi),
    ('/api/(company)_record/([0-9]+)', CompanyNGOApi),
    ('/api/(ngo)_record/([0-9]+)', CompanyNGOApi),
    ('/api/search/([a-z]+)', SearchApi),
    ('/api/search/([a-z]+)/([0-9]+)', SearchApi),
    ('/api/sysprop/(.+)', SystemPropertyApi),
    ('/api/pdf/([^/]+)', PdfStatusApi),
    ('/api/update/([a-z]+)', Update),
    ('/rss/changes/pending', PendingChangesRss)
], debug=True)
