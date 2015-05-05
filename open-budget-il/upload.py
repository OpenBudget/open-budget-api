import logging
import datetime

from google.appengine.api import search

from models import BudgetLine, SupportLine, ChangeLine, SearchHelper, PreCommitteePage, Entity
from models import ChangeExplanation, SystemProperty, ChangeGroup, CompanyRecord, NGORecord, ModelDocumentation
from models import ParticipantMapping, ParticipantTimeline, ParticipantPhoto, BudgetApproval, TrainingFlow
from models import MRExemptionRecord, MRExemptionRecordDocument, MRExemptionRecordHistory

def add_prefixes(item,code_field):
    code = item.get(code_field)
    if code is not None and len(code)>0:
        prefixes = [ code[:l] for l in range(2,len(code),2) ]
        prefixes.append(code)
        item["prefixes"] = prefixes

class UploadKind(object):
    FTS_FIELDS = []

    @staticmethod
    def mysetattr(response,i,k,v):
        # verify that the key exists in the model
        # there can be discreptancies 
        if hasattr(i, k):
            orig_v = i.__getattribute__(k)
            if type(orig_v) == list and type(v) == list:
                try:
                    orig_v.sort()
                    logging.debug("About to sort %s:%r" % (k,v))
                    v.sort()
                    if len(v) != len(orig_v) or any(x!=y for x,y in zip(v,orig_v)):
                        i.__setattr__(k,v)
                        response.write("%s: %s: %r != %r\n" % (i.key, k,orig_v,v))
                except ValueError:
                    i.__setattr__(k,v)
                    response.write("%s: %s: list != new list\n" % (i.key,k))
                return True
            else:
                if orig_v != v:
                    # TODO: not sure this is the proper handling of a new 'none'
                    if v == None:
                        if (type(orig_v) is list):
                            v = []
                        if (type(orig_v) is str):
                            v = ""
                        if (type(orig_v) is int):
                            v = 0
                    i.__setattr__(k,v)
                    response.write("%s: %s: %r != %r\n" % (i.key, k,orig_v,v))
                    return True
        return False

    def preprocess_item(self,item):
        return item

    def handle(self, response, item):
        to_delete = []
        item = self.preprocess_item(item)
        vals = [item[f] for f in self.KEY_FIELDS]
        if any(v is None for v in vals):
            return None
        key_args = zip(self.KEY_FIELDS,vals)
        query_args = [getattr(self.CLS, f)==val for f,val in key_args]
        dbitem = self.CLS.query(*query_args).fetch(100)
        if len(dbitem) == 0:
            classname = self.CLS.__name__
            item['_cls'] = classname
            response.write("No {0} for {1}".format(classname,
                                                    " ".join("%s=%s" % x for x in key_args)))
            dbitem = self.CLS()
        else:
            for x in dbitem[1:]:
                to_delete.append(x)
            dbitem = dbitem[0]
        dbitems = [dbitem]

        doc = None
        if len(self.FTS_FIELDS) > 0:
            # Build a unique document ID
            key_values = map(lambda x: str(getattr(dbitem, x)), self.KEY_FIELDS)
            doc_id = "%s-%s"%(self.KIND, "-".join(key_values))
            fieldList = []
            # Iterate over the FTS_FIELDS and build the field descriptor list
            for fieldDescriptor in self.FTS_FIELDS:
                field = getattr(search, fieldDescriptor['type'])(
                    name=fieldDescriptor['name'],
                    value=getattr(dbitem, fieldDescriptor['name']))

                fieldList.append(field)
            # Create a new document
            doc = search.Document(
                doc_id = doc_id,
                fields = fieldList)

        dirty = False
        dirty_fields = set()
        for k,v in item.iteritems():
            field_dirty = self.mysetattr(response,dbitem,k,v)
            if field_dirty:
                dirty = True
                dirty_fields.add(k)
        if not dirty:
            dbitems = []
        return dbitems, to_delete, doc

class ULSystemProperty(UploadKind):
    KIND = "sp"
    CLS = SystemProperty
    KEY_FIELDS = [ 'key' ]

class ULModelDocumentation(UploadKind):
    KIND = "md"
    CLS = ModelDocumentation
    KEY_FIELDS = [ 'model', 'field' ]

class ULParticipantPhoto(UploadKind):
    KIND = "pp"
    CLS = ParticipantPhoto
    KEY_FIELDS = [ 'name' ]

class ULTrainingFlow(UploadKind):
    KIND = "tf"
    CLS = TrainingFlow
    KEY_FIELDS = [ 'flow', 'index' ]

class ULBudgetApproval(UploadKind):
    KIND = "ba"
    CLS = BudgetApproval
    KEY_FIELDS = [ 'year' ]

    def preprocess_item(self,item):
        if item.get('approval_date') is not None:
            item['approval_date'] = datetime.datetime.fromtimestamp(item['approval_date']).date()
        if item.get('effect_date') is not None:
            item['effect_date'] = datetime.datetime.fromtimestamp(item['effect_date']).date()
        if item.get('end_date') is not None:
            item['end_date'] = datetime.datetime.fromtimestamp(item['end_date']).date()
        return item

class ULParticipantTimeline(UploadKind):
    KIND = "pt"
    CLS = ParticipantTimeline
    KEY_FIELDS = [ 'kind', 'full_title', 'start_date' ]

    def preprocess_item(self,item):
        if item.get('start_date') is not None:
            item['start_date'] = datetime.datetime.fromtimestamp(item['start_date']).date()
        if item.get('end_date') is not None:
            item['end_date'] = datetime.datetime.fromtimestamp(item['end_date']).date()
        return item

class ULParticipantMapping(UploadKind):
    KIND = "pm"
    CLS = ParticipantMapping
    KEY_FIELDS = [ 'budget_code' ]

class ULBudgetLine(UploadKind):
    KIND = "bl"
    CLS = BudgetLine
    KEY_FIELDS = [ 'year', 'code' ]
    FTS_FIELDS = [ {"name":"title", "type":"TextField"} ]

    def preprocess_item(self,item):
        code = item['code']
        add_prefixes(item, 'code')
        item["depth"] = len(code)/2 - 1
        return item

class ULChangeLine(UploadKind):
    KIND = "cl"
    CLS = ChangeLine
    KEY_FIELDS = [ 'year', 'leading_item', 'req_code', 'budget_code' ]

    def preprocess_item(self,item):
        add_prefixes(item,'code')
        if item.get('date') is not None and item['date'] != "":
            try:
                item['date'] = datetime.datetime.strptime(item['date'],'%d/%m/%Y')
            except:
                item['date'] = datetime.datetime.fromtimestamp(item['date']/1000.0+86400)
            item['date'] = item['date'].date()
        return item

class ULChangeGroup(UploadKind):
    KIND = "cg"
    CLS = ChangeGroup
    KEY_FIELDS = [ 'year', 'group_id' ]

    def preprocess_item(self,item):
        if item.get('date') is not None and item['date'] != "":
            item['date'] = datetime.datetime.strptime(item['date'],'%d/%m/%Y')
            item['date'] = item['date'].date()
        return item

class ULChangeExplanation(UploadKind):
    KIND = "ex"
    CLS = ChangeExplanation
    KEY_FIELDS = [ 'year', 'leading_item', 'req_code' ]

class ULSupportLine(UploadKind):
    KIND = "sl"
    CLS = SupportLine
    KEY_FIELDS = [ 'year', 'code', 'recipient', 'kind' ]

    def preprocess_item(self,item):
        add_prefixes(item,'code')
        return item

class ULSearchHelper(UploadKind):
    KIND = "sh"
    CLS = SearchHelper
    KEY_FIELDS = [ 'kind', 'value', 'year' ]

    def preprocess_item(self,item):
        item["prefix"] = None
        return item

class ULEntity(UploadKind):
    KIND = "en"
    CLS = Entity
    KEY_FIELDS = [ 'id', 'kind' ]

    def preprocess_item(self,item):
        try:
            item['creation_date'] = datetime.datetime.fromtimestamp(item['creation_date'])
        except:
            item['creation_date'] = None
        return item

class ULCompanyRecord(UploadKind):
    KIND = "cr"
    CLS = CompanyRecord
    KEY_FIELDS = [ 'registration_id' ]

class ULNGORecord(UploadKind):
    KIND = "ngo"
    CLS = NGORecord
    KEY_FIELDS = [ 'amuta_id' ]

class ULMRExemptionRecord(UploadKind):
    KIND = "mr"
    CLS = MRExemptionRecord
    KEY_FIELDS = [ 'publication_id' ]

    def preprocess_item(self,item):
        if item.get('supplier_id') is not None:
            item['supplier_id'] = str(item['supplier_id'])
        docs = []
        for doc in item.get('documents',[]):
            if doc['update_time'] != '-':
                doc['update_time'] = datetime.datetime.strptime("%(time)s %(date)s" % doc['update_time'],'%H:%M %d/%m/%Y')
            else:
                doc['update_time'] = None
            docs.append( MRExemptionRecordDocument(**doc) )
        item['documents'] = docs
        # history_items = []
        # for history_item in item.get('history',[]):
        #     if history_item['date'] != '-':
        #         history_item['date'] = datetime.datetime.strptime(history_item['date'],'%d/%m/%Y').date()
        #     else:
        #         history_item['date'] = None
        #     history_item['from_value'] = history_item.get('from')
        #     if history_item['from_value'] is not None:
        #         del history_item['from']
        #     history_item['to_value'] = history_item.get('to')
        #     if history_item['to_value'] is not None:
        #         del history_item['to']
        #     if type(history_item['to_value']) is list or type(history_item['from_value']) is list:
        #         continue
        #     logging.debug("adding history item %r" % history_item )
        #     history_items.append( MRExemptionRecordHistory(**history_item) )
        # item['history'] = history_items

        for f in ['start_date','end_date','claim_date','last_update_date']:
            d = item.get(f)
            if d is not None and d != '' and d != '-':
                item[f] = datetime.datetime.strptime(d,'%Y-%m-%d').date()
            else:
                item[f] = None

        add_prefixes(item,'budget_code')
        return item


upload_handlers = [
    ULSystemProperty,
    ULModelDocumentation,
    ULParticipantPhoto,
    ULTrainingFlow,
    ULBudgetApproval,
    ULParticipantTimeline,
    ULParticipantMapping,
    ULBudgetLine,
    ULChangeLine,
    ULChangeGroup,
    ULSearchHelper,
    ULEntity,
    ULCompanyRecord,
    ULNGORecord,
    ULMRExemptionRecord,
    ULSupportLine
]

upload_handlers = { x.KIND: x() for x in upload_handlers }
