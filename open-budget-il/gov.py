# encoding: utf8

import os
import webapp2
import json
import datetime
import re
import logging
import urllib
import itertools

from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.api import users

from models import BudgetLine, SearchHelper

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
 2015: 1.0/(1.017*1.023*1.016),
 2016: 1.0/(1.017*1.023*1.016*1.016)
}

class GovApi(webapp2.RequestHandler):

    def do_paging(self):
        return True

    def get_search(self,queryString,num,year=2014):
        parts = WORDS.findall(queryString)
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
        for rec in query.fetch(num,batch_size=num):
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

    def get(self,code):

        def intize(x,default):
            if x is None or x == '':
                x = default
            else:
                x = int(x)
            return x


        depth = intize(self.request.get('depth'),0)
        year = intize(self.request.get('year'),None)
        text = self.request.get('text')
        if text is not None and len(text)<1:
            text = None
        num = intize(self.request.get('num'),20)

        key = "GOV:"+ "/".join(unicode(x).encode('utf8') for x in [code,year,depth,text,num])
        data = memcache.get(key)
        if data is not None:
            ret = data.decode("zip")
        else:
            query = None
            if text is not None:
                query = self.get_search(text,num,year)
            elif code is not None:
                conditions = []
                if year is not None:
                    conditions.append( BudgetLine.year == year )
                if depth == 0:
                    conditions.append( BudgetLine.code == code )
                elif depth == 1:
                    conditions.append( BudgetLine.prefixes == code )
                    conditions.append( ndb.OR(BudgetLine.depth == len(code)/2,BudgetLine.depth == len(code)/2-1) )
                query = BudgetLine.query( ndb.AND(*conditions) )
            ret = query.order(-BudgetLine.year, -BudgetLine.net_allocated).fetch(batch_size=200)
            all_codes = [ x.prefixes for x in ret ]
            all_codes = set(itertools.chain(*all_codes))
            if len(all_codes)>0:
                if year is None:
                    all_codes_query = BudgetLine.query( BudgetLine.code.IN(all_codes) )
                else:
                    all_codes_query = BudgetLine.query( BudgetLine.code.IN(all_codes), BudgetLine.year == year )
            else:
                all_codes_query = []
            all_codes = {}
            for rec in all_codes_query:
                all_codes[(rec.year,rec.code)] = rec.title
            ret = [ {
                "parent": [
                    { "budget_id": x.code[:i], "title": all_codes.get((x.year,x.code[:i]),'') }
                    for i in range(len(x.code)-2,0,-2)
                ],
                "net_amount_revised": x.net_revised,
                "year": x.year,
                "title": x.title,
                "gross_amount_used": x.gross_used,
                "gross_amount_revised": x.gross_revised,
                "budget_id": x.code,
                "net_amount_used": x.net_used,
                "inflation_factor": INFLATION[x.year],
                "net_amount_allocated": x.net_allocated,
                "gross_amount_allocated": x.gross_allocated
            } for x in ret ]
            self.response.headers['Content-Type'] = 'application/json'
            ret = json.dumps(ret)
            memcache.add(key, ret.encode("zip"), 30)

        callback = self.request.get('callback')
        if callback is not None and callback != "":
            ret = "%s(%s);" % ( callback, ret )

        self.response.write(ret)

WORDS = re.compile(u'([א-ת0-9a-zA-Z]+)')

def prefix_starts_with(clz,prefix):
    next = prefix[:-1] + unichr(ord(prefix[-1])+1)
    return ndb.AND(clz.prefix>=prefix,clz.prefix<next)

def code_starts_with(clz,prefix):
    return ndb.AND(clz.code>=prefix,clz.code<prefix+'X')

gov = webapp2.WSGIApplication([
    ('/gov/api/([0-9]+)', GovApi),
], debug=True)
