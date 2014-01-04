import os
import urllib
import json
import logging

from google.appengine.api import users
from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.api import images
from google.appengine.ext import ndb
from google.appengine.api import files

import jinja2
import webapp2


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class PreCommitteePage(ndb.Model):
    """One page from one blob"""
    pdf = ndb.BlobKeyProperty()
    page = ndb.BlobKeyProperty()
    leading_item = ndb.IntegerProperty() 
    req_code = ndb.IntegerProperty() 

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
     
        img = images.Image(jpg)
        if img.width < img.height:
            jpg = images.rotate(jpg,90,quality=100)
            yield jpg
            jpg = images.rotate(jpg,180,quality=100)
            yield jpg
        else:
            yield jpg

        i = iend


class UploadFile(blobstore_handlers.BlobstoreUploadHandler):
    
    def post(self):

        upload_files = self.get_uploads('file')  # 'file' is file upload field in the form
        blob_info = upload_files[0]

        pdf = blobstore.BlobReader(blob_info.key()).read()

        logging.info("Attmempting to extract images from PDF of %d bytes" % len(pdf))
        pages = extract_images_from_pdf(pdf)

        to_put = []
        for page in pages:
            logging.info("got an image")
            file_name = files.blobstore.create(mime_type='image/jpeg')
            with files.open(file_name, 'a') as f:
                f.write(page)
            files.finalize(file_name)
            blob_key = files.blobstore.get_blob_key(file_name)
            
            p = PreCommitteePage(pdf=blob_info.key(), page=blob_key)
            to_put.append(p)
        ndb.put_multi(to_put)
            
        self.response.headers['Content-Type'] = 'application/json'   
        obj = {
            'success': 'true', 
            'id': str(blob_info.key())
        } 
        self.response.out.write(json.dumps(obj))


class Request(webapp2.RequestHandler):
    
    def get(self):

        requestId = self.request.get("id")

        pages = PreCommitteePage.query(PreCommitteePage.pdf==blobstore.BlobKey(requestId))
        pages = [ { 'pageId' : str(i), 'image': images.get_serving_url(f.page,size=900,crop=False) } for i,f in enumerate(pages) ]

        request = {
            'id': requestId,
            'pages': pages,
            'pages_json': json.dumps(pages),
            'committeeDate': 1388527200000,
            'requestDate': 1388354400000
        } # TODO: get this object from DB

        if requestId is None:
           template_values = {}
            # TODO: create a page with a list of all requests
        else:
            template_values = {                
                'request': request
            }
            template_name = 'requestEdit.html'

        template = JINJA_ENVIRONMENT.get_template(template_name)
        self.response.write(template.render(template_values))

    def post(self):

        reqDate = self.request.get("requestDate")
        comDate = self.request.get("committeeDate")
        fileUrl = self.request.get("requestFileUrl")

        query_params = {'id': fileUrl}  # TODO:  replace with the created request's ID
        self.redirect('/change_input/request?' + urllib.urlencode(query_params))


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
    ('/change_input/request', Request),
    ('/change_input/page', Page)
], debug=True)
