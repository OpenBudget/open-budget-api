from google.appengine.ext import db
from google.appengine.tools import bulkloader

from models import *

class BudgetLineLoader(bulkloader.Loader):
    def __init__(self):
        bulkloader.Loader.__init__(self, 'BudgetLine',
                                   [('code', lambda x: x.decode('utf-8')),
                                    ('year', int),
                                    ('title', lambda x: x.decode('utf-8')),
                                    ('net_allocated',int),
                                    ('gross_allocated',int),
                                    ('net_revised',int),
                                    ('gross_revised',int),
                                    ('net_used',int),
                                    ('gross_used',int),
                                   ])

loaders = [BudgetLineLoader]
