import os
import webapp2
import json
import jinja2
import datetime

from google.appengine.api import memcache
from google.appengine.ext import ndb

from models import BudgetLine, SupportLine, ChangeLine

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
        to_update = self.request.body.split('\n')
        to_update = [ json.loads(x) for x in to_update ]
        to_put = []
        for item in to_update:
            if what == "bl":
                dbitem = BudgetLine.query(BudgetLine.year==item['year'],BudgetLine.code==item['code']).fetch(1)
                if len(dbitem) == 0:
                    self.response.write("No budget item for year=%d, code=%s" % (item['year'],item['code']))
                    dbitem = BudgetLine()
                    code = item['code']
                    prefixes = [ code[:l] for l in range(2,len(code),2) ]
                    prefixes.append(code)
                    self.response.write(code+"==>"+prefixes+"\n")
                    dbitem.prefixes = prefixes
                    dbitem.depth = len(code)/2 - 1
                else:
                    dbitem = dbitem[0]
                for k,v in item.iteritems():
                    dbitem.__setattr__(k,v)
                to_put.append(dbitem)
            if what == "cl":
                dbitem = ChangeLine.query(ChangeLine.year==item['year'],
                                          ChangeLine.leading_item==item['leading_item'],
                                          ChangeLine.req_code==item['req_code'],
                                          ChangeLine.budget_code==item['budget_code']).fetch(1)
                if len(dbitem) == 0:
                    self.response.write("No change item for year=%(year)d, leading_item=%(leading_item)d, req_code=%(req_code)d, code=%(budget_code)s" % item)
                    dbitem = ChangeLine()
                    code = item['budget_code']
                    prefixes = [ code[:l] for l in range(2,len(code),2) ]
                    prefixes.append(code)
                    self.response.write(code+"==>"+repr(prefixes)+"\n")
                    dbitem.prefixes = prefixes
                else:
                    for x in dbitem[1:]:
                        x.delete()
                    dbitem = dbitem[0]
                if item.get('date') is not None and item['date'] != "":
                    item['date'] = datetime.datetime.strptime(item['date'],'%d/%m/%Y')
                for k,v in item.iteritems():
                    dbitem.__setattr__(k,v)
                to_put.append(dbitem)
        ndb.put_multi(to_put)
        self.response.write("OK\n")

    
class MainPage(webapp2.RequestHandler):

    def get(self,code,year=None):
        self.response.headers['Content-Type'] = 'application/json'
        if year != None:
            year = int(year)
            lines = BudgetLine.query(BudgetLine.code==code,BudgetLine.year==year)
        else:
            lines = BudgetLine.query(BudgetLine.code==code)
        ret = [ x.to_dict() for x in lines ]
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
                                         BudgetLine.year==year).fetch_async()
            prefixes = [ prefix for prefix in rec.prefixes if prefix != "00" ]
            prefixes = [ (len(prefix)/2, prefix) for prefix in prefixes ]
            hierarchy_queries = [ (depth,
                                   BudgetLine.query(code_starts_with(BudgetLine,prefix), 
                                                    BudgetLine.year==year, 
                                                    BudgetLine.depth==depth).order(BudgetLine.code).fetch_async(batch_size=100))
                                  for depth, prefix in prefixes ]
            history_query = BudgetLine.query(BudgetLine.code==code).fetch_async(batch_size=100)
            support_query = SupportLine.query(SupportLine.prefixes==code).order(SupportLine.year).fetch_async(batch_size=100)
            changes_query = ChangeLine.query(ChangeLine.prefixes==code).fetch_async(batch_size=100)

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
                                              'recepients':{}}
                recepient = supports[support_code]['recepients'].setdefault(support['recepient'],{})
                recepient.setdefault('sum',0)
                recepient.setdefault('count',0)
                recepient['sum'] += support['amount_used']*INFLATION[support['year']] / INFLATION[2013]
                recepient['count'] += 1

                l = recepient.setdefault('kinds',{}).setdefault(support['kind'],[])
                l.append({'year':support['year'],
                          'num_supported':support['num_supported'],
                          'amount_used':support['amount_used'],
                          'amount_allocated':support['amount_allocated']})

            ## changes
            changes = [ {'date':'-' if rec.date is None else rec.date.strftime("%d/%m/%Y"),
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
            memcache.add(key, ret.encode("zip"), 3660)

        self.response.headers['Content-Type'] = 'application/json'
        if callback is not None and callback != "":
            ret = "%s(%s);" % ( callback, ret )
        self.response.write(ret)

            
api = webapp2.WSGIApplication([
    ('/api/([0-9]+)', MainPage),
    ('/api/([0-9]+)/([0-9]+)', MainPage),
    ('/api/update/([a-z]+)', Update)
], debug=True)
report = webapp2.WSGIApplication([
    ('/report/api/([0-9]{8})/([0-9]{4})', Report),
    ('/report/all/([0-9]{4})', ReportAll),
], debug=True)

