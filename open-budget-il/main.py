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
import itertools

from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.api import users

from models import BudgetLine, SupportLine, ChangeLine, SearchHelper, PreCommitteePage, Entity
from models import ChangeExplanation, SystemProperty, ChangeGroup, CompanyRecord, NGORecord, ModelDocumentation
from models import ParticipantMapping, ParticipantTimeline, ParticipantPhoto, BudgetApproval, TrainingFlow
from models import MRExemptionRecord, MRExemptionRecordDocument, MRExemptionRecordHistory
from secret import ALLOWED_EMAILS, UPLOAD_KEY
from upload import upload_handlers

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

        # check if we are in a production or localhost environment
        if ("localhost" in self.request.host):
            # on a localhost the body needs to be unquoted
            body = urllib.unquote_plus(self.request.body)
        else:
            body = self.request.body
        body = body.strip("=")
        to_update = body.split('\n')
        try:
            to_update = [ json.loads(x) for x in to_update if x.strip() != '' ]
        except Exception,e:
            print body
            raise
        to_put = []
        to_delete = []
        handler = upload_handlers[what]
        for item in to_update:
            items, todel = handler.handle(self.response,item)
            to_delete.extend(todel)
            to_put.extend(items)

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
        elif type(o) == set:
            return list(o)
        return json.JSONEncoder.default(self, o)

def HTMLEncode(data, fields):
    header = u"<thead>%s</thead>" % "".join( u"<th style='border: 1px solid black'>%s</th>" % f['he'] for f in fields )
    body = "".join( u"<tr>%s</tr>" % "".join( u"<td style='border: 1px solid black'>%s</td>" % (row[f['field']] if row[f['field']] is not None else "") for f in fields ) for row in data )
    table = "<table style='border-collapse:collapse'>%s<tbody>%s</tbody></table>" % (header,body)
    return table.encode('utf8')

def CSVEncode(data,fields):
    output = StringIO.StringIO()
    writer = csv.writer(output)
    writer.writerow([f['he'].encode('utf8') for f in fields])
    for row in data:
        writer.writerow([unicode(row[f['field']]).encode('utf8') for f in fields])
    return output.getvalue()

def XLSEncode(data,fields):
    output = StringIO.StringIO()
    writer = csv.writer(output)
    writer.writerow([f['he'].encode('cp1255','ignore') for f in fields])
    for row in data:
        writer.writerow([unicode(row[f['field']]).encode('cp1255','ignore') for f in fields])
    return output.getvalue()

def get_participants(budget_code,year=None,month=None,day=None):
    code = budget_code[2:4]
    ret = []
    mapping = ParticipantMapping.query(ParticipantMapping.budget_code==code).fetch(1)
    if len(mapping) > 0:
        mapping = mapping[0]
        participants = mapping.participants
    else:
        participants = []
    participant_mapping = ['pm','finance']+participants+['fin_com']
    date = None
    if year is not None and month is not None and day is not None:
        date = datetime.date(year=int(year),month=int(month),day=int(day))
        participants = ParticipantTimeline.query(ParticipantTimeline.kind.IN(participant_mapping),ParticipantTimeline.start_date<=date).order(-ParticipantTimeline.start_date).fetch(250)
    else:
        participants = ParticipantTimeline.query(ParticipantTimeline.kind.IN(participant_mapping)).order(ParticipantTimeline.start_date).fetch(250)
    for kind in participant_mapping:
        kind_ret = []
        for participant in participants:
            if participant.kind == kind:
                if date is None or participant.end_date is None or participant.end_date>date:
                    rec = participant.to_dict()
                    photo = ParticipantPhoto.query(ParticipantPhoto.name==participant.name).fetch(1)
                    if len(photo)>0:
                        photo_url = u"/api/thumbnail/%s" % participant.name
                        photo_url = urllib.quote(photo_url.encode('utf8'))
                        rec['photo_url'] = "http://the.open-budget.org.il" + photo_url
                    kind_ret.append(rec)
        kind_ret.sort(key=lambda(x):x['title'])
        ret.extend(kind_ret)
    return ret

class GenericApi(webapp2.RequestHandler):

    def _set_response_headers(self):
        self.response.headers['Content-Type'] = 'application/json'
        self.response.headers['Access-Control-Allow-Origin'] = "*"
        self.response.headers['Access-Control-Max-Age'] = '604800'
        self.response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type, If-Match, If-Modified-Since, If-None-Match, If-Unmodified-Since, X-Requested-With, Cookie'
        self.response.headers['Access-Control-Allow-Credentials'] = 'true'

    def do_paging(self):
        return True

    def getDocumentation(self,kind):
        fields = ModelDocumentation.query(ModelDocumentation.model==kind,ModelDocumentation.order>=0).order(ModelDocumentation.order).fetch(25)
        fields = [ r.to_dict() for r in fields ]
        return fields

    def options(self,*args,**kw):
        self._set_response_headers()
        self.response.write('{}')

    def get(self,*args,**kw):
        self._set_response_headers()
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
        if self.output_format not in ['html','json','csv','xls']:
            self.output_format = 'json'

        data = None
        key = self.key(*args,**kw)
        if key is not None:
            key = key + "//%s/%s/%s" % (self.first,self.limit,self.output_format)
            data = memcache.get(key)
        if data is not None:
            ret = data.decode("zip")

        else:
            query = self.get_query(*args,**kw)
            if isinstance(query,ndb.Query):
                if self.do_paging():
                    ret = [ x.to_dict() for x in query.fetch(batch_size=self.first+self.limit,limit=self.limit,offset=self.first) ]
                else:
                    ret = [ x.to_dict() for x in query.fetch(batch_size=self.limit) ]
            else:
                ret = query
            if self.output_format == 'json':
                self._set_response_headers()
                if self.single and len(ret)>0:
                    ret = ret[0]
                ret = CustomJSONEncoder().encode(ret)
            elif self.output_format == 'html':
                ret = HTMLEncode(ret, self.getDocumentation(query.kind))
            elif self.output_format == 'csv':
                ret = CSVEncode(ret, self.getDocumentation(query.kind))
            elif self.output_format == 'xls':
                ret = XLSEncode(ret, self.getDocumentation(query.kind))
            if key is not None:
                memcache.add(key, ret.encode("zip"), 86400)

        if self.output_format == 'json':
            callback = self.request.get('callback')
            if callback is not None and callback != "":
                ret = "%s(%s);" % ( callback, ret )
                self.response.headers['Content-Type'] = 'text/javascript'
        elif self.output_format == 'html':
            self.response.headers['Content-Type'] = 'text/html'
        elif self.output_format == 'csv':
            self.response.headers['Content-Type'] = 'text/csv'
            self.response.headers['Content-Disposition'] = 'attachment; filename=export.csv'
        elif self.output_format == 'xls':
            self.response.headers['Content-Type'] = 'application/vnd.ms-excel'
            self.response.headers['Content-Disposition'] = 'attachment; filename=export.csv'

        self.response.headers['cache-control'] = 'public, max-age=600'
        self.response.write(ret)

aggregated_budget_fields = set(k for k,v in BudgetLine.__dict__.iteritems()
                               if isinstance(v,ndb.IntegerProperty)  or isinstance(v,ndb.FloatProperty))
aggregated_budget_fields.remove('year')
aggregated_budget_fields.remove('depth')

class BudgetApi(GenericApi):

    def key(self,code,year=None,kind=None,extra=None):
        return "BudgetApi:%s/%s/%s/%s" % (code,year,kind,extra)

    def get_query(self,code,year=None,kind=None,extra=None):
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
            elif kind == "depth":
                depth = int(extra)
                lines = BudgetLine.query(code_starts_with(BudgetLine,code),BudgetLine.depth==depth,BudgetLine.year==year)
            elif kind == "equivs":
                equiv_code = "E%s/%s" % (year,code)
                _lines = BudgetLine.query(BudgetLine.equiv_code==equiv_code).order(BudgetLine.year).fetch(batch_size=50)
                lines = []
                by_year = itertools.groupby(_lines, lambda x:x.year)
                for year, yearly in by_year:
                    rec = { 'year': year,
                            'code': code,
                            'title': _lines[-1].title,
                            'orig_codes':[] }
                    base = dict((k,None) for k in aggregated_budget_fields)
                    for item in yearly:
                        for k,v in item.to_dict().iteritems():
                            if k in aggregated_budget_fields and v is not None:
                                rec.setdefault(k,0)
                                rec[k] += v
                        rec['orig_codes'].append(item.code)
                    base.update(rec)
                    lines.append(base)
        else:
            lines = BudgetLine.query(BudgetLine.code==code).order(BudgetLine.year)
        return lines

class BudgetApprovalsApi(GenericApi):

    def key(self,*args,**kw):
        return "BudgetApprovalsApi:%s" % "/".join(args)

    def get_query(self,budget_code):
        return BudgetApproval.query().order(BudgetApproval.year)

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
        code = leading_item = req_code = year = equivs = None
        if len(args) == 1:
            code = args[0]
        elif len(args) == 2:
            code, year = args
        elif len(args) == 3:
            code, year, equivs = args

        if '-' in code:
            transfer_id = code
            self.single = True
            code = None
        if year is not None:
            year = int(year)
            if code is not None:
                if equivs is not None:
                    equiv_code = "E%s/%s" % (year,code)
                    lines = ChangeGroup.query(ChangeGroup.equiv_code==equiv_code).order(-ChangeGroup.date)
                else:
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

class ExemptionsApi(GenericApi):

    def key(self,*args,**kw):
        return "ExemptionsApi:%s" % "/".join(args)

    def get_query(self,*args,**kw):
        kind = args[0]
        lines = None
        if kind=='publication':
            publication_id = args[1]
            publication_id = int(publication_id)
            lines = MRExemptionRecord.query(MRExemptionRecord.publication_id==publication_id)
            self.single = True
        elif kind=='budget':
            budget_code = args[1]
            lines = MRExemptionRecord.query(MRExemptionRecord.prefixes==budget_code)
        elif kind=='updated':
            date_from = datetime.date(int(args[1]),int(args[2]),int(args[3]))
            date_to = datetime.date(int(args[4]),int(args[5]),int(args[6]))
            lines = MRExemptionRecord.query(MRExemptionRecord.last_update_date >= date_from, MRExemptionRecord.last_update_date <= date_to)
        elif kind=='new':
            lines = MRExemptionRecord.query().order(-MRExemptionRecord.last_update_date)

        return lines

class SupportsApi(GenericApi):

    def key(self,*args):
        if args[0] == 'recipient':
            if len(args)>2:
                return "SupportsApi:%s/%s" % (args[1].encode('hex'),args[2])
            else:
                return "SupportsApi:%s" % args[1].encode('hex')
        else:
            return "SupportsApi:%s" % "/".join([str(a) for a in args])

    def aggregate_lines(self,lines,aggregate_fields=['title']):
        ret = {}
        sum_fields = ['amount_supported','amount_allocated','num_used']
        collect_fields = ['entity_kind','recipient','entity_id']

        items, next_curs, more = lines.fetch_page(100)
        while len(items) > 0:
            for item in items:
                item = item.to_dict()
                key = item['title']
                rec = ret.setdefault(key,{f:item[f] for f in aggregate_fields})
                for f in sum_fields:
                    rec[f] = rec.setdefault(f,0) + item[f]
                collected = tuple(item[f] for f in collect_fields)
                rec.setdefault('collected',set()).add(collected)
                rec.setdefault('collected_fields',collect_fields)
            if more:
                items, next_curs, more = lines.fetch_page(100,start_cursor=next_curs)
            else:
                break

        return ret.values()

    def get_query(self,*args):
        if args[0] == 'recipient':
            recipient = args[1].decode('utf8')
            recipients = list(set([ recipient, recipient[:35] ]))
            if len(args)>2:
                year=int(args[2])
                lines = SupportLine.query(SupportLine.year==year,SupportLine.recipient.IN(recipients)).order(SupportLine.code,SupportLine.kind,SupportLine.year)
            else:
                lines = SupportLine.query(SupportLine.recipient.IN(recipients)).order(SupportLine.code,SupportLine.kind,SupportLine.year)
        elif args[0] == 'kind':
            logging.error('SupportsApi:kind args=%r' % (args,))
            kind = args[1]
            if len(args)>2:
                code = args[2]
                if len(args)>3:
                    if args[3] == 'aggregated':
                        lines = SupportLine.query(SupportLine.entity_kind==kind,SupportLine.prefixes==code)
                        lines = self.aggregate_lines(lines,['title'])
                    else:
                        year = int(args[3])
                        lines = SupportLine.query(SupportLine.entity_kind==kind,SupportLine.prefixes==code,SupportLine.year==year)
                        logging.error('SupportsApi:kind args=%r' % (args,))
                        if len(args)>4:
                            if args[4] == 'aggregated':
                                lines = self.aggregate_lines(lines,['title','year'])
                            else:
                                assert(False)
                else:
                    lines = SupportLine.query(SupportLine.entity_kind==kind,SupportLine.prefixes==code)
            else:
                lines = SupportLine.query(SupportLine.entity_kind==kind)
        else:
            code = args[0]
            if len(args)>1:
                year=int(args[1])
                lines = SupportLine.query(SupportLine.year==year,SupportLine.prefixes==code).order(SupportLine.recipient,SupportLine.kind,SupportLine.year)
            else:
                lines = SupportLine.query(SupportLine.prefixes==code).order(SupportLine.recipient,SupportLine.kind,SupportLine.year)
        return lines

class SystemPropertyApi(GenericApi):

    def key(self,key):
        return "SystemPropertyApi:%s" % key

    def get_query(self,key):
        lines = SystemProperty.query(SystemProperty.key==key)
        self.single = True
        return lines


ALL_DIGITS = re.compile(r'^\d+$')
class EntityApi(GenericApi):

    def key(self,id):
        return "Entity:%s" % id

    def get_query(self,id):
        lines = []
        if ALL_DIGITS.match(id) is not None:
            lines = Entity.query(Entity.id==id).fetch(1)
        else:
            lines = Entity.query(Entity.name==id).fetch(1)
        if len(lines)>0:
            ret = lines[0].to_dict()
            id = ret['id']
            logging.debug('entity-api: id='+id)
            supports = SupportLine.query(SupportLine.entity_id==id).order(-SupportLine.year).fetch(1000)
            ret['supports'] = [x.to_dict() for x in supports]
            exemptions = MRExemptionRecord.query(MRExemptionRecord.entity_id==id).order(-MRExemptionRecord.start_date).fetch(1000)
            ret['exemptions'] = [x.to_dict() for x in exemptions]
            return ret
        else:
            return {}

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

class ParticipantApi(GenericApi):

    def key(self,*args,**kw):
        return "ParticipantApi:%s" % "/".join(args)

    def get_query(self,budget_code,year=None,month=None,day=None):
        return get_participants(budget_code,year,month,day)

class TrainingFlowApi(GenericApi):

    def key(self,*args,**kw):
        return "TrainingFlowApi:%s" % "/".join(args)

    def get_query(self,flow):
        return TrainingFlow.query(TrainingFlow.flow==flow).order(TrainingFlow.index)

class DescribeApi(GenericApi):

    def key(self,*args,**kw):
        return "DescribeApi:%s" % "/".join(args)

    def get_query(self,model):
        return ModelDocumentation.query(ModelDocumentation.model==model).order(ModelDocumentation.order)


class ThumbnailApi(webapp2.RequestHandler):

    def get(self,name):
        name=name.decode('utf8')
        photo = ParticipantPhoto.query(ParticipantPhoto.name==name).fetch(1)
        if len(photo)>0:
            photo = photo[0]
        else:
            logging.info("can't find photo for name %r" % name)
            self.abort(403)
        self.response.headers['Content-Type'] = 'image/png'
        self.response.headers['cache-control'] = 'public, max-age=86400'
        data = photo.photo_url
        if data.startswith('data'):
            data = data.split(',',1)[1]
        data = data.decode('base64')
        self.response.write(data)

WORDS = re.compile(u'([א-ת0-9a-zA-Z]+)')

class SearchApi(GenericApi):

    def do_paging(self):
        return False

    def get_querystr(self):
        try:
            return self.request.get('q')
        except:
            qs = self.request.query_string
            if 'q=' in qs:
                qs = qs[qs.index('q=')+2:]
                qs = qs.split('&')[0]
                return urllib.unquote(qs).decode('windows-1255')
            else:
                return None

    def key(self,kind,year=None):
        queryString = self.get_querystr()
        return "SearchApi:%s/%s/%s" % (kind,year,queryString)

    def get_query(self,kind,year=None):

        queryString = self.get_querystr()
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

class PeriodicTasks(webapp2.RequestHandler):

    def get(self):
        pass

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
            memcache.add(key, ret.encode("zip"), 86400)

        self.response.headers['Content-Type'] = 'application/json'
        if callback is not None and callback != "":
            ret = "%s(%s);" % ( callback, ret )
        self.response.write(ret)

api = webapp2.WSGIApplication([
    ('/api/budget/([0-9]+)/approvals', BudgetApprovalsApi),

    ('/api/budget/([0-9]+)', BudgetApi),
    ('/api/budget/([0-9]+)/([0-9]+)', BudgetApi),
    ('/api/budget/([0-9]+)/([0-9]+)/(equivs)', BudgetApi),
    ('/api/budget/([0-9]+)/([0-9]+)/(kids)', BudgetApi),
    ('/api/budget/([0-9]+)/([0-9]+)/(parents)', BudgetApi),
    ('/api/budget/([0-9]+)/([0-9]+)/(depth)/([0-9]+)', BudgetApi),
    ('/api/changes/([0-9]+)', ChangesApi),
    ('/api/changes/pending/(all)', ChangesPendingApi),
    ('/api/changes/pending/(committee)', ChangesPendingApi),
    ('/api/changes/([0-9]+)/([0-9]+)', ChangesApi),
    ('/api/changes/([0-9][0-9])-([0-9][0-9][0-9])/([0-9]+)', ChangesApi),

    ('/api/changegroup/([0-9]+)', ChangeGroupApi),
    ('/api/changegroup/pending', ChangeGroupsPendingApi),
    ('/api/changegroup/([0-9]+)/([0-9]+)', ChangeGroupApi),
    ('/api/changegroup/([0-9]+)/([0-9]+)/(equivs)', ChangeGroupApi),
    ('/api/changegroup/([0-9][0-9]-[0-9][0-9][0-9])/([0-9]+)', ChangeGroupApi),

    ('/api/change_expl/([0-9][0-9])-([0-9][0-9][0-9])/([0-9]+)', ChangeExplApi),
    ('/api/supports/(kind)/([a-z]+) ', SupportsApi),
    ('/api/supports/(kind)/([a-z]+)/([0-9]+)', SupportsApi),
    ('/api/supports/(kind)/([a-z]+)/([0-9]+)/([0-9]+)', SupportsApi),
    ('/api/supports/(kind)/([a-z]+)/([0-9]+)/(aggregated)', SupportsApi),
    ('/api/supports/(kind)/([a-z]+)/([0-9]+)/([0-9]+)/(aggregated)', SupportsApi),
    ('/api/supports/(recipient)/([^/]+)/([0-9]+)', SupportsApi),
    ('/api/supports/(recipient)/(.+)', SupportsApi),
    ('/api/supports/([0-9]+)', SupportsApi),
    ('/api/supports/([0-9]+)/([0-9]+)', SupportsApi),

    ('/api/exemption/(publication)/([0-9]+)', ExemptionsApi),
    ('/api/exemption/(budget)/([0-9]+)', ExemptionsApi),
    ('/api/exemption/(new)', ExemptionsApi),
    ('/api/exemption/(updated)/([0-9][0-9][0-9][0-9])-([0-9][0-9])-([0-9][0-9])/([0-9][0-9][0-9][0-9])-([0-9][0-9])-([0-9][0-9])', ExemptionsApi),

    ('/api/thumbnail/(.+)', ThumbnailApi),
    ('/api/participants/([0-9]+)', ParticipantApi),
    ('/api/participants/([0-9]+)/([0-9]+)/([0-9]+)/([0-9]+)', ParticipantApi),
    ('/api/training/(.+)', TrainingFlowApi),
    ('/api/entity/(.+)', EntityApi),

    ('/api/describe/(.+)', DescribeApi),

    ('/api/(company)_record/([0-9]+)', CompanyNGOApi),
    ('/api/(ngo)_record/([0-9]+)', CompanyNGOApi),
    ('/api/search/([a-z]+)', SearchApi),
    ('/api/search/([a-z]+)/([0-9]+)', SearchApi),
    ('/api/sysprop/(.+)', SystemPropertyApi),
    ('/api/pdf/([^/]+)', PdfStatusApi),
    ('/api/update/([a-z]+)', Update),
    ('/rss/changes/pending', PendingChangesRss)
], debug=True)

tasks = webapp2.WSGIApplication([
    ('/tasks/periodic', PeriodicTasks),
], debug=True)

redirect = webapp2.WSGIApplication([
    webapp2.Route('/', webapp2.RedirectHandler, defaults={'_uri':'/stg/'}),
])
