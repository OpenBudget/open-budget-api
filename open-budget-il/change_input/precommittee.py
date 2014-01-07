import os
import urllib
import json
import logging
import datetime

from google.appengine.api import users
from google.appengine.api import images
from google.appengine.api import files
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext import ndb
from google.appengine.ext import deferred

import jinja2
import webapp2

from models import PreCommitteePage


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class MainPage(webapp2.RequestHandler):

   def get(self):
       upload_url = blobstore.create_upload_url('/change_input/uploadFile')
       template_values = {
           'uploadURL': upload_url
       };
       template = JINJA_ENVIRONMENT.get_template('home.html')
       self.response.headers['Content-Type'] = 'text/html; charset=utf-8'   
       self.response.write(template.render(template_values))

def extract_images_from_pdf(pdf):
    startmark = "\xff\xd8"
    startfix = 0
    endmark = "\xff\xd9"
    endfix = 2
    i = 0
    while True:
        istream = pdf.find("stream", i)
        if istream < 0:
            logging.info("couldn't find start of stream at %d: %r" % (i,pdf[:100]))
            break
        istart = pdf.find(startmark, istream, istream+20)
        if istart < 0:
            i = istream+20
            logging.info("couldn't find startmart of stream at %d: %r" % (istream,pdf[istream:istream+20]))
            continue
        iend = pdf.find("endstream", istart)
        if iend < 0:
            logging.info("Didn't find end of stream!")
            return
        iend = pdf.find(endmark, iend-20)
        if iend < 0:
            logging.info("Didn't find end of stream!")
            return
     
        istart += startfix
        iend += endfix
        jpg = pdf[istart:iend]
        logging.info("Got one image %d-%d" % (istart,iend))
        yield jpg

        i = iend

def split_pdf_to_pages(pdf_key):
    pdf = blobstore.BlobReader(pdf_key).read()

    logging.info("Attmempting to extract images from PDF of %d bytes" % len(pdf))
    pages = extract_images_from_pdf(pdf)

    to_wait = []
    last = None
    for page in pages:
        file_name = files.blobstore.create(mime_type='image/jpeg')
        with files.open(file_name, 'a') as f:
            f.write(page)
        files.finalize(file_name)
        blob_key = files.blobstore.get_blob_key(file_name)
        
        p = PreCommitteePage(pdf=pdf_key, page=blob_key)
        to_wait.extend( ndb.put_multi_async([p]) )
        last = p

    ndb.Future.wait_all( to_wait )
    
    if last != None:
        last.last = True
        ndb.put_multi([last])

class UploadFile(blobstore_handlers.BlobstoreUploadHandler):
    
    def post(self):

        upload_files = self.get_uploads('file')  # 'file' is file upload field in the form
        blob_info = upload_files[0]

        deferred.defer(split_pdf_to_pages,blob_info.key(),_queue="pdfqueue")
            
        self.response.headers['Content-Type'] = 'application/json'   
        obj = {
            'success': 'true', 
            'id': str(blob_info.key())
        } 
        self.response.out.write(json.dumps(obj))


class Request(webapp2.RequestHandler):
    
    def get(self):

        pdfId = self.request.get("pdfId")
        comDate = self.request.get("comDate")

        committee_items = PreCommitteePage.query(PreCommitteePage.pdf==blobstore.BlobKey(pdfId))
        committee_items = [ { 'pageId' : str(f.page), 'image': images.get_serving_url(f.page,size=900,crop=False) } for f in committee_items ]

        committee = {
            'id': pdfId,
            'committee_items': committee_items,
            'committee_items_json': json.dumps(committee_items),
            'committeeDate': int(comDate)
        } 

        if pdfId is None:
           template_values = {}
            # TODO: create a page with a list of all requests
        else:
            template_values = {                
                'committee': committee
            }
            template_name = 'committee.html'

        template = JINJA_ENVIRONMENT.get_template(template_name)
        self.response.write(template.render(template_values))

    def post(self):
        
        comDate = self.request.get("committeeDateVal")
        pdfId = self.request.get("requestFileUrl")

        comDate = datetime.datetime.fromtimestamp(int(comDate)/1000.0)
        to_put = []
        for page in PreCommitteePage.query(PreCommitteePage.pdf==blobstore.BlobKey(pdfId)):
            page.date = comDate
            page.year = comDate.year
            to_put.append(page)
        ndb.put_multi(to_put)
        
        query_params = {'pdfId': pdfId, 'comDate': self.request.get("committeeDateVal") }  
        self.redirect('/change_input/committee?' + urllib.urlencode(query_params))


class Page(webapp2.RequestHandler):

    def post(self):

        arr = self.request.POST.dict_of_lists()

        # TODO: save post data to DB

        self.response.headers['Content-Type'] = 'application/json'   
        resp = {
            'success': 'true'
            # 'test': arr
        } 
        self.response.out.write(json.dumps(resp))



application = webapp2.WSGIApplication([
    ('/change_input/', MainPage),
    ('/change_input/uploadFile', UploadFile),
    ('/change_input/committee', Request),
    ('/change_input/page', Page)
], debug=True)
