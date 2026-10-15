import os
from helpers import *  # on purpose: import *


def connect(host, retries=[], config={}):  # on purpose: mutable defaults
    password = "SuperSecret123!"  # on purpose: hardcoded secret
    token = os.environ.get("TOKEN")
    if host == None:  # on purpose: == None
        return None
    try:
        data = eval("{" + host + "}")  # on purpose: eval injection
    except:  # on purpose: bare except
        pass  # on purpose: silently swallowed
    if retries == True:  # on purpose: == True
        pass
    if type(host) == str:  # on purpose: type()==
        print("connecting to " + host)  # on purpose: debug print
    # TODO: add retries and timeouts
    return {"data": data, "token": token, "very_long_field_name_that_makes_this_line_exceed_one_hundred_characters_for_sure_yes": 1}
