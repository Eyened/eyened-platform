from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from eyened_orm.base import Base
from eyened_orm.project import Contact


@dataclass(frozen=True, slots=True)
class LookupPart:
    column: str
    source: "Entity | None"


@dataclass(frozen=True, slots=True)
class Lookup:
    parts: tuple[LookupPart, ...]

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(part.column for part in self.parts)

    @property
    def tokens(self) -> tuple["Entity | None", ...]:
        return tuple(part.source for part in self.parts)


@dataclass(frozen=True, slots=True)
class Implication:
    """Parent relationship when creating or seeding an entity."""

    parent: "Entity"
    attribute: str
    required: bool = True


def req(parent: "Entity", attribute: str) -> Implication:
    """Required parent; missing parent is an error."""
    return Implication(parent, attribute, True)


def opt(parent: "Entity", attribute: str) -> Implication:
    """Optional parent (nullable FK); skip attach/seed when absent."""
    return Implication(parent, attribute, False)


@dataclass(slots=True, eq=False)
class Entity:
    model: type[Base]
    pk_column: str | tuple[str, ...]
    pk_row_field: str
    lookups: tuple[Lookup, ...]
    fields: Mapping[str, str]
    non_mutable: frozenset[str] = frozenset()
    anonymous_identity: str | None = None
    implies: tuple[Implication, ...] = ()

    @property
    def lookup(self) -> Lookup:
        return self.lookups[0]

    @property
    def lookup_columns(self) -> tuple[str, ...]:
        return self.lookup.columns

    @property
    def lookup_tokens(self) -> tuple[str | "Entity", ...]:
        return self.lookup.tokens

    @property
    def name(self) -> str:
        return self.model.__tablename__

    def __repr__(self) -> str:
        return f"Entity({self.name})"


def key(column: str, source: "Entity | None" = None) -> LookupPart:
    return LookupPart(column=column, source=source)


def lookup(*parts: LookupPart) -> Lookup:
    return Lookup(parts=parts)


CONTACT = Entity(
    model=Contact,
    pk_column="ContactID",
    pk_row_field="contact_id",
    lookups=(
        lookup(
            key("Name"),
            key("Email"),
            key("Institute"),
        ),
    ),
    fields={
        "Name": "contact_name",
        "Email": "contact_email",
        "Institute": "contact_institute",
        "Orcid": "contact_orcid",
    },
)
