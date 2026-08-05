from pydantic import BaseModel, ConfigDict

class StandardReqSetStruct(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    url: str
    method: str
    params: dict | None
    headers: dict | None
    ssl: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "StandardReqSetStruct": return cls.model_validate(data)

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

class StandardReqYAMLSetStruct(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    method: str
    path: str
    params: dict | None = None
    headers: dict | None = None
    form: dict | None = None
    body: dict | None = None
    ssl: bool | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "StandardReqYAMLSetStruct": return cls.model_validate(data)

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
