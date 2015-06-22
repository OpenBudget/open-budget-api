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
import urllib2

from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import blobstore
from google.appengine.api import users
from google.appengine.api import search

from models import BudgetLine, SupportLine, ChangeLine, SearchHelper, PreCommitteePage, Entity
from models import ChangeExplanation, SystemProperty, ChangeGroup, CompanyRecord, NGORecord, ModelDocumentation
from models import ParticipantMapping, ParticipantTimeline, ParticipantPhoto, BudgetApproval, TrainingFlow
from models import MRExemptionRecord, MRExemptionRecordDocument, ChangeLine
from secret import ALLOWED_EMAILS, UPLOAD_KEY
from upload import upload_handlers
from xml.etree import ElementTree as et

path = os.path.join(os.path.dirname(__file__),'templates')

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(path),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class SearchEngineBudget(webapp2.RequestHandler):

    def get(self,kind=None,value=None):
        self.response.headers['Content-Type'] = 'text/html'
        se_template = JINJA_ENVIRONMENT.get_template('index.html')

        url = 'g2'
        if kind is not None:
            url += '/'+str(kind)
            if value is not None:
                url += '/'+str(value)

        to_render = { 'title': u'פותחים את תקציב המדינה',
                      'url': url,
                      'kind': kind,
                      'hash': '' }

        if kind == 'bl' and value is not None and len(value)>1:
            code = value
            year = 2014
            budget = BudgetLine.query(BudgetLine.code=="00"+code,BudgetLine.year==year).fetch(1)
            if len(budget)>0:
                budget = budget[0]
                parent_codes = [ "00"+code[:x] for x in range(0,len(code)+1,2) ]
                parents = BudgetLine.query(BudgetLine.code.IN(parent_codes),BudgetLine.year==year).fetch(10)
                parents = [ { 'url': 'g2/bl/'+p.code[2:], 'title':p.title, 'index': i } for i,p in enumerate(parents) ]

                to_render.update({ 'title': u'תקציב '+budget.title,
                                   'code': code,
                                   'url': 'g2/bl/'+code,
                                   'hash': 'budget/%s/%s/main' % (code,year),
                                   'net_revised': budget.net_revised,
                                   'breadcrumbs': parents[1:] })
        elif kind == 'tr':
            pass
        elif kind == 'en':
            pass
        elif kind == 'main':
            pass
        elif kind == 'spending':
            pass


        to_render.setdefault('code','')
        to_render.setdefault('year',2014)
        to_render.setdefault('net_revised',0)
        to_render.setdefault('breadcrumbs',[])

        out = se_template.render(to_render)
        self.response.write(out)


main = webapp2.WSGIApplication([
    ('/g2/(.+)/(.*)', SearchEngineBudget),
    ('/', SearchEngineBudget),
], debug=True)
