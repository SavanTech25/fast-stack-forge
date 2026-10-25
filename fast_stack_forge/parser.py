from dataclasses import dataclass
from typing import Optional

PYTHON_TYPE_MAP = {
    "string": "str", "int": "int", "float": "float",
    "bool": "bool", "text": "str", "date": "date", "datetime": "datetime",
}
SQLALCHEMY_TYPE_MAP = {
    "string": "String(255)", "int": "Integer", "float": "Float",
    "bool": "Boolean", "text": "Text", "date": "Date", "datetime": "DateTime",
}
PYDANTIC_TYPE_MAP = {
    "string": "str", "int": "int", "float": "float",
    "bool": "bool", "text": "str", "date": "date", "datetime": "datetime",
}

@dataclass
class FieldDef:
    name: str
    type: str
    encrypt: bool = False
    hash: bool = False
    nullable: bool = False
    foreign_key: Optional[str] = None

    @property
    def python_type(self):
        base = PYTHON_TYPE_MAP.get(self.type, "str")
        return f"Optional[{base}]" if self.nullable else base

    @property
    def sqlalchemy_type(self):
        return SQLALCHEMY_TYPE_MAP.get(self.type, "String(255)")

    @property
    def pydantic_type(self):
        base = PYDANTIC_TYPE_MAP.get(self.type, "str")
        return f"Optional[{base}]" if self.nullable else base

    @property
    def needs_date_import(self):
        return self.type in ("date", "datetime")

    @property
    def fk_table(self):
        if not self.foreign_key:
            return None
        # same pluralisation as make:entity's table names
        name = self.foreign_key.lower()
        return name if name.endswith("s") else name + "s"

    @property
    def fk_column(self):
        return self.name + "_id" if self.foreign_key else None


def parse_fields(raw_fields: tuple) -> list:
    result = []
    for token in raw_fields:
        parts = token.split(":")
        if len(parts) < 2:
            raise ValueError(f"Invalid field '{token}'. Expected: name:type[:modifier]")
        name, raw_type = parts[0], parts[1].lower()
        if raw_type not in PYTHON_TYPE_MAP:
            raise ValueError(f"Unknown type '{raw_type}'. Valid: {', '.join(PYTHON_TYPE_MAP.keys())}")
        modifiers = parts[2:]
        foreign_key = None
        for mod in modifiers:
            if mod.startswith("fk="):
                foreign_key = mod[3:]
        result.append(FieldDef(
            name=name, type=raw_type,
            encrypt="encrypt" in modifiers,
            hash="hash" in modifiers,
            nullable="nullable" in modifiers,
            foreign_key=foreign_key,
        ))
    return result
