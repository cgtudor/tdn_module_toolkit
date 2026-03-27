from pydantic import BaseModel
from typing import Optional, List, Any


class ItemProperty(BaseModel):
    """Represents an item property on an item."""
    property_name: int
    property_name_resolved: Optional[str] = None
    subtype: Optional[int] = None
    subtype_resolved: Optional[str] = None
    cost_table: Optional[int] = None
    cost_value: Optional[int] = None
    cost_value_resolved: Optional[str] = None
    param1: Optional[int] = None
    param1_value: Optional[int] = None
    chance_appear: Optional[int] = None


class ScriptVariable(BaseModel):
    """Represents a script variable from VarTable."""
    name: str
    var_type: int  # 1=int, 2=float, 3=string
    value: Any  # int, float, or str depending on var_type

    @property
    def type_name(self) -> str:
        """Return human-readable type name."""
        return {1: "int", 2: "float", 3: "string"}.get(self.var_type, "unknown")


class ScriptVariableInput(BaseModel):
    """Model for creating/updating a script variable."""
    name: str
    var_type: int  # 1=int, 2=float, 3=string
    value: Any  # int, float, or str depending on var_type


class ItemSummary(BaseModel):
    """Summary info for item list views."""
    resref: str
    name: str
    base_item: int
    cost: int
    stack_size: int
    identified: bool


class ItemDetail(BaseModel):
    """Full item details including properties."""
    resref: str
    name: str
    localized_name: Optional[dict] = None
    description: Optional[str] = None
    localized_description: Optional[dict] = None
    tag: str
    base_item: int
    cost: int
    additional_cost: int = 0
    stack_size: int
    charges: int = 0
    cursed: bool = False
    identified: bool = True
    plot: bool = False
    stolen: bool = False
    palette_id: Optional[int] = None
    comment: Optional[str] = None
    properties: List[ItemProperty] = []
    variables: List[ScriptVariable] = []
    raw_data: Optional[dict] = None


class ItemCreate(BaseModel):
    """Model for creating a new item."""
    resref: str
    name: str
    tag: Optional[str] = None
    base_item: int
    cost: int = 0
    stack_size: int = 1


class ItemUpdate(BaseModel):
    """Model for updating an item."""
    name: Optional[str] = None
    tag: Optional[str] = None
    cost: Optional[int] = None
    stack_size: Optional[int] = None
    identified: Optional[bool] = None
    charges: Optional[int] = None
    cursed: Optional[bool] = None
    plot: Optional[bool] = None


class LocalizedStringUpdate(BaseModel):
    """Model for updating localized string fields."""
    text: Optional[str] = None  # Direct text (language 0)
    string_ref: Optional[int] = None  # TLK reference


class ItemPropertyInput(BaseModel):
    """Model for creating/updating an item property."""
    property_name: int
    subtype: int = 0
    cost_table: int = 0
    cost_value: int = 0
    param1: int = 255
    param1_value: int = 0
    chance_appear: int = 100


class ItemTemplateUpdate(BaseModel):
    """Model for updating an item template."""
    # Basic fields
    name: Optional[LocalizedStringUpdate] = None
    description: Optional[LocalizedStringUpdate] = None
    desc_identified: Optional[LocalizedStringUpdate] = None
    tag: Optional[str] = None
    cost: Optional[int] = None
    additional_cost: Optional[int] = None
    stack_size: Optional[int] = None
    charges: Optional[int] = None

    # Flags
    identified: Optional[bool] = None
    plot: Optional[bool] = None
    cursed: Optional[bool] = None
    stolen: Optional[bool] = None

    # Properties (full replacement)
    properties: Optional[List[ItemPropertyInput]] = None

    # Script variables (full replacement)
    variables: Optional[List[ScriptVariableInput]] = None

    # Model parts (icon/appearance)
    model_part1: Optional[int] = None
    model_part2: Optional[int] = None
    model_part3: Optional[int] = None

    # Advanced (triggers rename/palette updates)
    new_resref: Optional[str] = None
    palette_category: Optional[int] = None
