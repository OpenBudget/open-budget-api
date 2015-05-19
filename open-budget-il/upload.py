#encoding: utf8

import logging
import datetime
import re

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
    FTS_TOKENIZE_FIELDS = []
    FTS_VERSION = 2
    VERSION_FIELD_NAME = 'ver_auto'
    TOKENS_FIELD_NAME = 'tokens_auto'

    @staticmethod
    def mysetattr(response,i,k,v):
        # verify that the key exists in the model
        # there can be discreptancies
        if hasattr(i, k):
            orig_v = i.__getattribute__(k)
            if type(orig_v) == list and type(v) == list:
                try:
                    orig_v.sort()
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

    def handle(self, response, item, current_doc):
        to_delete = []
        item = self.preprocess_item(item)
        vals = [item[f] for f in self.KEY_FIELDS]
        if any(v is None for v in vals):
            return None
        key_args = zip(self.KEY_FIELDS,vals)
        query_args = [getattr(self.CLS, f)==val for f,val in key_args]
        dbitem = self.CLS.query(*query_args).fetch(100)
        classname = self.CLS.__name__
        if len(dbitem) == 0:
            item['_cls'] = classname
            response.write("No {0} for {1}".format(classname,
                                                    " ".join("{0}".format(x) for x in key_args)))
            dbitem = self.CLS()
        else:
            for x in dbitem[1:]:
                to_delete.append(x)
            dbitem = dbitem[0]
        dbitems = [dbitem]

        dirty = False
        dirty_fields = set()
        for k,v in item.iteritems():
            field_dirty = self.mysetattr(response,dbitem,k,v)
            if field_dirty:
                dirty = True
                dirty_fields.add(k)

        doc = None
        # Update the document if the dirty_fields contain any of the FTS_FIELDS
        fts_field_names = map(lambda x: x[0], self.FTS_FIELDS)
        dirty_fts_fields = set(fts_field_names).intersection(dirty_fields)
        logging.debug("dirty_fts_fields: %r, current_doc=%r, current_ver=%r" % \
                        (dirty_fts_fields,current_doc,current_doc[self.VERSION_FIELD_NAME] if current_doc is not None else "N/A"))
        if len(dirty_fts_fields) > 0 or current_doc is None or current_doc[self.VERSION_FIELD_NAME] is None or current_doc[self.VERSION_FIELD_NAME]  < self.FTS_VERSION:
            doc_id = self.get_doc_id(item)
            logging.debug('doc_id=%s' % doc_id)
            fieldList = [search.TextField(name="type", value=classname),
                         search.NumberField(name=self.VERSION_FIELD_NAME, value=self.FTS_VERSION)]
            # Iterate over the FTS_FIELDS and build the field descriptor list
            for name, field_type in self.FTS_FIELDS:
                field = getattr(search, field_type)(
                    name=name,
                    value=item[name])

                fieldList.append(field)
            tokens = set()
            logging.debug('self.FTS_TOKENIZE_FIELDS=%s' % self.FTS_TOKENIZE_FIELDS)
            for field in self.FTS_TOKENIZE_FIELDS:
                tokens.update(self.get_tokens(item[field]))
            if len(tokens)>0:
                logging.debug(u'tokenized -> %r' % (tokens))
                fieldList.append(search.TextField(name=self.TOKENS_FIELD_NAME,value=" ".join(tokens)))
            logging.debug('fieldList=%r' % fieldList)
            # Create a new document
            doc = search.Document(
                doc_id = doc_id,
                fields = fieldList,
                rank = self.get_doc_rank(item))

        if not dirty:
            dbitems = []
        return dbitems, to_delete, doc

    def get_doc_id(self,item):
        # Build a unique document ID
        key_values = map(lambda x: unicode(item.get(x)).encode('utf8').encode('hex'), self.KEY_FIELDS)
        doc_id = "%s-%s"%(self.KIND, "-".join(key_values))
        return doc_id

    def get_doc_rank(self,item):
        # Returns ranking for the document (None if N/A)
        return None

    def get_search_query(self, queryString, request):
        searchQueryParts = []#queryString, "type=%s"%self.KIND]
        for field, typ in self.FTS_FIELDS:
            fieldVal = request.get(field)
            if len(fieldVal) > 0:
                searchQueryParts.append("%s=%s"%(field, fieldVal))

        if len(searchQueryParts) > 0:
            return "(%s)"%" AND ".join(searchQueryParts)
        else:
            return None

    WORDS = re.compile(u'([א-ת0-9a-zA-Z]+)')

    def get_tokens(self,string):
        # Find all distinct words
        splits = self.WORDS.findall(string)
        # Remove potential initials
        subsplits = [ x[1:] for x in splits if x[0] in [u'ה', u'ב', u'ו', u'מ', u'ב', u'כ', u'ל'] and len(x) > 3 ]
        splits.extend(subsplits)
        tokens = set()
        # Get all prefixes
        for split in splits:
            tokens.update(set([ split[:l] for l in range(1,len(split)+1) ]))
        logging.debug(u'tokenizing %s -> %r' %(string,tokens))
        return tokens

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
    FTS_FIELDS = [
        ('code','TextField'),
        ('title','TextField'),
        ('year','NumberField'),
    ]
    FTS_TOKENIZE_FIELDS = ['title']

    def preprocess_item(self,item):
        code = item['code']
        add_prefixes(item, 'code')
        item["depth"] = len(code)/2 - 1
        return item

    def get_doc_rank(self,item):
        # rank = int("1"+"%08d"%int("0"+item['code'][2:]))
        # rank = 200000000 - rank
        # rank = rank * 40 + item['year']
        rank = max(item.get('net_revised',0),0)
        return rank

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
    FTS_FIELDS = [
        ('id','TextField'),
        ('name','TextField'),
    ]
    FTS_TOKENIZE_FIELDS = ['name']

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
        item['history'] = None
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
            dateFormat = None
            if d is not None and d != '' and d != '-':
                if '-' in d:
                    dateFormat = '%Y-%m-%d'
                elif '/' in d:
                    dateFormat = '%d/%m/%Y'

            if dateFormat is not None:
                item[f] = datetime.datetime.strptime(d,dateFormat).date()
            else:
                # Unknown format or empty date field
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
