from google.appengine.ext import ndb

class SystemProperty(ndb.Model):
    """A system property"""
    key = ndb.StringProperty()
    value = ndb.JsonProperty(indexed=False)
    last_modified = ndb.DateTimeProperty(auto_now=True)

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

    recipient = ndb.StringProperty()

    company_id = ndb.StringProperty()
    ngo_id = ndb.StringProperty()

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
    # 0  - approved
    # 1  - approximate
    # 10 - pending
    date_type = ndb.IntegerProperty()

    prefixes = ndb.StringProperty(repeated=True)

class ChangeExplanation(ndb.Model):
    """Change request explanation"""
    year = ndb.IntegerProperty()
    leading_item = ndb.IntegerProperty()
    req_code = ndb.IntegerProperty()

    explanation = ndb.TextProperty(indexed=False)

class ChangeGroup(ndb.Model):
    """Aggregated change group"""
    year = ndb.IntegerProperty()
    group_id = ndb.StringProperty()
    transfer_ids = ndb.StringProperty(repeated=True)
    budget_codes = ndb.StringProperty(repeated=True)
    req_titles = ndb.StringProperty(repeated=True)
    prefixes = ndb.StringProperty(repeated=True)
    titles = ndb.JsonProperty()
    title_value = ndb.IntegerProperty()
    title_template = ndb.StringProperty()
    changes = ndb.JsonProperty()
    date = ndb.DateProperty()
    pending = ndb.BooleanProperty()

class SearchHelper(ndb.Model):
    """Text Search index"""
    year = ndb.IntegerProperty(repeated=True)
    kind = ndb.StringProperty()
    prefix = ndb.StringProperty()
    value = ndb.StringProperty()
    priority = ndb.IntegerProperty()
    tokens = ndb.StringProperty(repeated=True)


class PreCommitteePage(ndb.Model):
    """One page from one blob"""
    pdf = ndb.BlobKeyProperty()
    page = ndb.BlobKeyProperty()
    year = ndb.IntegerProperty()
    request_id = ndb.StringProperty(repeated=True)  ## XX-YYY % (leading-item, req_code)
    date = ndb.DateProperty()
    last = ndb.BooleanProperty()
    kind = ndb.IntegerProperty() # 1 for request explanation, 2 for table

class CompanyRecord(ndb.Model):
    """A single company record"""
    registration_id = ndb.StringProperty()
    registration_date = ndb.StringProperty()
    registration_year = ndb.IntegerProperty()
    name_heb = ndb.StringProperty()
    name_eng = ndb.StringProperty()
    description = ndb.StringProperty()
    goals = ndb.StringProperty()
    status = ndb.StringProperty()
    kind = ndb.StringProperty()
    kind_gov = ndb.StringProperty()
    kind_restrictions = ndb.StringProperty()
    last_report_year = ndb.IntegerProperty()
    status_offender = ndb.StringProperty()
    address_country = ndb.StringProperty()
    address_city = ndb.StringProperty()
    address_street = ndb.StringProperty()
    address_house_num = ndb.StringProperty()
    address_zipcode = ndb.StringProperty()
    address_pob = ndb.StringProperty()
    address_at = ndb.StringProperty()

class NGORecord(ndb.Model):
    """A single amuta record"""
    amuta_id = ndb.StringProperty()
    name_heb = ndb.StringProperty()
    kind = ndb.StringProperty()
    category = ndb.StringProperty()
    founding_year = ndb.IntegerProperty()
    essence = ndb.StringProperty()
    objective = ndb.StringProperty()
