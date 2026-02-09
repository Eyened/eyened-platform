from typing import TypeVar

SettingsType = TypeVar("SettingsType")


def pretty_settings(cls: SettingsType) -> SettingsType:
    def _repr_pretty_(self, p, cycle: bool) -> None:
        if cycle:
            p.text(f"{self.__class__.__name__}(...)")
            return
        p.text(self.__str__())

    def __repr__(self) -> str:
        # Use __str__ for human readable, multiline and aligned output
        return self.__str__()

    def __str__(self) -> str:
        data = self.model_dump()
        if not data:
            return ""
        width = max(len(str(k)) for k in data)
        lines = "\n".join(f"{str(k).ljust(width)} : {v}" for k, v in data.items())
        return lines

    cls._repr_pretty_ = _repr_pretty_
    cls.__repr__ = __repr__
    cls.__str__ = __str__
    return cls
