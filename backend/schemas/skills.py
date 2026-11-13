"""Pydantic接口数据格式；复用已有校验，保持前端JSON兼容。"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ..skills.store import validate_library, validate_skill


class SkillPayload(BaseModel):
    schemaVersion: Literal[1] = 1
    id: str = Field(default="", description="新增时可留空，由接口生成；修改时保留原ID")
    name: str = Field(max_length=120, description="技能名称")
    job: str = Field(max_length=120, description="转职名称")
    damageType: Literal["physical", "magic", "none"]
    targeting: Literal["single", "all"] = Field(
        default="single", description="伤害范围：单体技能或群体技能"
    )
    healingRecipient: Literal["self", "allAllies"] = Field(
        default="self", description="回复范围：单体（当前血量最低）或群体存活角色"
    )
    cooldown: float = Field(allow_inf_nan=False, description="技能冷却秒数，可为负数")
    lifesteal: float = Field(default=0, ge=0, le=100, description="技能吸血百分比")
    hitRate: float = Field(ge=0, le=100, description="命中百分数")
    criticalRate: float = Field(ge=0, le=100, description="暴击百分数")
    coefficients: dict[str, float] = Field(
        description="力量、魔力、技巧、速度、体质、血量和武威系数"
    )
    raceBonus: dict[str, Any] = Field(description="race与multiplier；other对应界面的黑暗")
    effect: dict[str, Any] | None = Field(description="null、debuff或buff；使用现有编辑器数据格式")

    @model_validator(mode="before")
    @classmethod
    def check_skill(cls, value):
        return validate_skill(value, generate_id=True)


class SkillLibraryPayload(BaseModel):
    schemaVersion: Literal[1] = 1
    skills: list[SkillPayload] = Field(max_length=5000)

    @model_validator(mode="before")
    @classmethod
    def check_library(cls, value):
        return validate_library(value)
