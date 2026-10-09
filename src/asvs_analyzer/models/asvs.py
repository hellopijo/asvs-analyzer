"""Lossless models for the inspected, hierarchical ASVS 5.0.0 format."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from asvs_analyzer.config import SUPPORTED_VERSION

Text = Annotated[str, Field(min_length=1)]
Ordinal = Annotated[int, Field(gt=0)]


class OfficialModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True, populate_by_name=True)

    @field_validator("*", mode="after")
    @classmethod
    def nonblank(cls, value):
        if isinstance(value, str) and not value.strip():
            raise ValueError("Text must not be blank")
        return value


class Requirement(OfficialModel):
    id: str = Field(alias="Shortcode", pattern=r"^V[1-9]\d*\.[1-9]\d*\.[1-9]\d*$")
    ordinal: Ordinal = Field(alias="Ordinal")
    description: Text = Field(alias="Description")
    level: Literal["1", "2", "3"] = Field(alias="L")


class Section(OfficialModel):
    id: str = Field(alias="Shortcode", pattern=r"^V[1-9]\d*\.[1-9]\d*$")
    ordinal: Ordinal = Field(alias="Ordinal")
    name: Text = Field(alias="Name")
    requirements: list[Requirement] = Field(alias="Items", min_length=1)


class Chapter(OfficialModel):
    id: str = Field(alias="Shortcode", pattern=r"^V[1-9]\d*$")
    ordinal: Ordinal = Field(alias="Ordinal")
    short_name: Text = Field(alias="ShortName")
    name: Text = Field(alias="Name")
    sections: list[Section] = Field(alias="Items", min_length=1)


class ScopedRequirement(BaseModel):
    """A requirement and its original hierarchy, for downstream consumers."""
    model_config = ConfigDict(frozen=True)
    requirement: Requirement
    chapter_id: str
    chapter_name: str
    section_id: str
    section_name: str


class Dataset(OfficialModel):
    name: Text = Field(alias="Name")
    short_name: Literal["ASVS"] = Field(alias="ShortName")
    version: Literal[SUPPORTED_VERSION] = Field(alias="Version")
    description: Text = Field(alias="Description")
    chapters: list[Chapter] = Field(alias="Requirements", min_length=1)

    @model_validator(mode="after")
    def validate_hierarchy(self):
        seen: set[str] = set()

        def check(node, parent=None):
            if node.id in seen:
                raise ValueError(f"Duplicate identifier: {node.id}")
            seen.add(node.id)
            if parent and node.id.rsplit(".", 1)[0] != parent:
                raise ValueError(f"Identifier {node.id} does not belong to {parent}")
            suffix = node.id.rsplit(".", 1)[-1].removeprefix("V")
            if int(suffix) != node.ordinal:
                raise ValueError(f"Ordinal does not match identifier: {node.id}")

        for chapter in self.chapters:
            check(chapter)
            for section in chapter.sections:
                check(section, chapter.id)
                for requirement in section.requirements:
                    check(requirement, section.id)
        return self

    def select_level(self, level: int) -> list[ScopedRequirement]:
        """Include all requirements with a minimum level <= selected level."""
        if type(level) is not int or level not in (1, 2, 3):
            raise ValueError("Verification level must be an integer: 1, 2, or 3")
        return [
            ScopedRequirement(
                requirement=requirement,
                chapter_id=chapter.id,
                chapter_name=chapter.name,
                section_id=section.id,
                section_name=section.name,
            )
            for chapter in self.chapters
            for section in chapter.sections
            for requirement in section.requirements
            if int(requirement.level) <= level
        ]
