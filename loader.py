def load_budget_line(input_dict, instance, bulkload_state_copy):
    code = instance['code']
    prefixes = [ code[:l] for l in range(2,len(code),2) ]
    prefixes.append(code)
    print code,"==>",prefixes
    instance['prefixes'] = prefixes
    instance['depth'] = len(code)/2 - 1
    return instance

def load_support_line(input_dict, instance, bulkload_state_copy):
    code = "00" + instance['code']
    instance['code'] = code
    prefixes = [ code[:l] for l in range(2,len(code),2) ]
    prefixes.append(code)
    instance['prefixes'] = prefixes
    return instance

def load_change_line(input_dict, instance, bulkload_state_copy):
    code = instance['budget_code']
    prefixes = [ code[:l] for l in range(2,len(code),2) ]
    prefixes.append(code)
    instance['prefixes'] = prefixes
    return instance
