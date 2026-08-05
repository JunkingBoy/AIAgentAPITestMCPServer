from enum import Enum

class StandardBusinessResultEnum(Enum):
    '''
    标准业务响应状态码和信息结果枚举
    '''
    # 标准请求异常
    SUCCESS = (1001, "操作成功")
    FAIL = (1002, "操作失败")
    ERROR = (1003, "操作异常")
    MISSING = (1004, "请求参数错误")
    UNFOUND = (1005, "未找到相关数据")

    @classmethod
    def get_msg_by_code(cls, code: int) -> str:
        for item in cls:
            if item.value[0] == code: return item.value[1]
        return "未知业务状态码"
