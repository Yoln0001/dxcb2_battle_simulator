from typing import Any, Literal
from pydantic import BaseModel, Field, model_validator, ConfigDict
from ..equipment.validation import validate_equipment, validate_library

class EquipmentPayload(BaseModel):
    model_config = ConfigDict(extra="allow")
    schemaVersion: Literal[1] = 1
    id: str = ''
    name: str = Field(max_length=120)
    category: Literal['weapon', 'armor', 'accessory', 'stone']
    weaponJob: str = ''
    attackType: Literal['physical', 'magic', 'none', 'receivedPhysical', 'receivedMagic']
    effectName: str = ''
    triggerEffectName: str = ''
    triggerEffects: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    triggerEnabled: bool = False
    startingBuff: dict[str, Any]
    triggerRate: float = Field(ge=0, le=100)
    effect: dict[str, Any] | None

    @model_validator(mode='before')
    @classmethod
    def validate_item(cls, value):
        return validate_equipment(value, generate_id=True)

class EquipmentLibraryPayload(BaseModel):
    schemaVersion: Literal[1] = 1
    equipment: list[EquipmentPayload] = Field(max_length=5000)

    @model_validator(mode='before')
    @classmethod
    def validate_items(cls, value):
        return validate_library(value)
