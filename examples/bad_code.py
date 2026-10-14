import os
from helpers import *  # 故意：import *


def connect(host, retries=[], config={}):  # 故意：可变默认参数
    password = "SuperSecret123!"  # 故意：硬编码密钥
    token = os.environ.get("TOKEN")
    if host == None:  # 故意：== None
        return None
    try:
        data = eval("{" + host + "}")  # 故意：eval 注入风险
    except:  # 故意：裸 except
        pass  # 故意：静默吞掉异常
    if retries == True:  # 故意：== True
        pass
    if type(host) == str:  # 故意：type()==
        print("connecting to " + host)  # 故意：调试 print
    # TODO: 加重试与超时
    return {"data": data, "token": token, "very_long_field_name_that_makes_this_line_exceed_one_hundred_characters_for_sure_yes": 1}
