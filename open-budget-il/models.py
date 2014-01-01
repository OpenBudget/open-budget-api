from google.appengine.ext import ndb

class BudgetLine(ndb.Model):
    """Single budget line"""
    code = ndb.StringProperty()
    title = ndb.StringProperty()
    year = ndb.IntegerProperty()

    net_allocated = ndb.IntegerProperty()
    gross_allocated = ndb.IntegerProperty()

    net_revised = ndb.IntegerProperty()
    gross_revised = ndb.IntegerProperty()

    net_used = ndb.IntegerProperty()
    gross_used = ndb.IntegerProperty()

    prefixes = ndb.StringProperty(repeated=True)
    depth = ndb.IntegerProperty()

class SupportLine(ndb.Model):
    """Single support line"""
    year = ndb.IntegerProperty()
    subject = ndb.StringProperty()
    code = ndb.StringProperty()
    title = ndb.StringProperty()
    kind = ndb.StringProperty()

    amount_supported = ndb.IntegerProperty()
    amount_allocated = ndb.IntegerProperty()
    num_used = ndb.IntegerProperty()
    
    recepient = ndb.StringProperty()
    
    prefixes = ndb.StringProperty(repeated=True)

class ChangeLine(ndb.Model):
    """Single change line"""
    year = ndb.IntegerProperty()
    leading_item = ndb.IntegerProperty() 
    req_code = ndb.IntegerProperty() 
    req_title = ndb.StringProperty() 
    change_code = ndb.IntegerProperty() 
    change_title = ndb.StringProperty()
    change_type_id = ndb.IntegerProperty()
    change_type_name = ndb.StringProperty() 
    committee_id = ndb.IntegerProperty() 
    budget_code = ndb.StringProperty()
    budget_title = ndb.StringProperty()
    net_expense_diff = ndb.IntegerProperty()
    gross_expense_diff = ndb.IntegerProperty()
    allocated_income_diff = ndb.IntegerProperty()
    commitment_limit_diff = ndb.IntegerProperty()
    personnel_max_diff = ndb.FloatProperty()
    date = ndb.DateProperty()
    explanation = ndb.TextProperty(indexed=False)

    prefixes = ndb.StringProperty(repeated=True)

class SearchHelper(ndb.Model):
    """Text Search index"""
    year = ndb.IntegerProperty(repeated=True)
    kind = ndb.StringProperty()
    prefix = ndb.StringProperty()
    value = ndb.StringProperty()
    priority = ndb.IntegerProperty()
    tokens = ndb.StringProperty(repeated=True)
