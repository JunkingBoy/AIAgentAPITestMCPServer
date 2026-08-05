from dataclasses import dataclass
from typing import Generic, TypeVar

from enums.StandardBusEnum import StandardBusinessResultEnum

T = TypeVar('T')
DataT = TypeVar('DataT')

@dataclass
class StandardLayerStructTemplate(Generic[T]):
    '''
    标准全局业务层响应模板
    '''
    status: StandardBusinessResultEnum
    data: T | None = None
    message: str | None = None

    @property
    def is_success(self) -> bool: return self.status == StandardBusinessResultEnum.SUCCESS
    @property
    def is_error(self) -> bool: return self.status != StandardBusinessResultEnum.SUCCESS
    @property
    def msg(self) -> str: return self.message or self.status.value[1]
    @staticmethod
    def ok(data: DataT | None = None) -> 'StandardLayerStructTemplate[DataT]': return StandardLayerStructTemplate(status=StandardBusinessResultEnum.SUCCESS, data=data)
    @classmethod
    def fail(cls, message: str | None = None) -> 'StandardLayerStructTemplate': return cls(status=StandardBusinessResultEnum.FAIL, message=message)
    @classmethod
    def error(cls, message: str | None = None) -> 'StandardLayerStructTemplate': return cls(status=StandardBusinessResultEnum.ERROR, message=message)
    @classmethod
    def missing(cls, message: str | None = None) -> 'StandardLayerStructTemplate': return cls(status=StandardBusinessResultEnum.MISSING, message=message)
    @classmethod
    def not_found(cls, message: str | None = None) -> 'StandardLayerStructTemplate': return cls(status=StandardBusinessResultEnum.UNFOUND, message=message)
