from pydantic import BaseModel, ConfigDict

class StandardDBConnectParamsStruct(BaseModel):
    '''
    标准数据库连接参数模板
    '''
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    host: str
    port: int
    user: str
    password: str
    database: str | None

    @classmethod
    def from_dict(cls, data: dict) -> "StandardDBConnectParamsStruct": return cls.model_validate(data)

    @classmethod
    def required(cls) -> list[str]:
        '''返回没有默认值的必填字段名列表'''
        return [
            name
            for name, field in cls.model_fields.items()
            if field.is_required()
        ]

    @property
    def info(self) -> dict: return self.model_dump(mode="json")

    def key_list(self) -> list[str]: return list(self.info.keys())

class StandardDBStepStruct(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    profile: str # 加入映射层
    table: str
    action: str # 行为枚举
    fields: list[str] | None = None
    where: dict | None = None
    expected: bool | None = None   # True=有结果, False=无结果, None=不校验

    @classmethod
    def from_dict(cls, data: dict) -> "StandardDBStepStruct": return cls.model_validate(data)

    @classmethod
    def required(cls) -> list[str]:
        '''返回没有默认值的必填字段名列表'''
        return [
            name
            for name, field in cls.model_fields.items()
            if field.is_required()
        ]

    @property
    def info(self) -> dict: return self.model_dump(mode="json")

    def key_list(self) -> list[str]: return list(self.info.keys())
