from datetime import datetime
from typing import Optional
from beanie import Document
from pydantic import Field, HttpUrl


class RootCauseItem(Document):
    title: str = Field(..., description="The title of the archival resource")
    link: HttpUrl = Field(...,
                          description="The direct URL link to the primary resource")
    description: Optional[str] = Field(
        None, description="A detailed summary of what the resource contains"
    )
    attribution: str = Field(...,
                             description="The organization or owner credited with the item")

    # Defaults to the exact moment the document is saved to the database.
    # The alias ensures Python writes/reads 'created_at', but MongoDB saves it exactly as 'createdAt'.
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        alias="createdAt",
        description="Timestamp of when the record was created"
    )

    resourceformat: str = Field(
        ..., description="The format of the resource (e.g., website, pdf, video)")
    contentcategory: str = Field(
        ..., description="The category classification (e.g., archives, person, place)")
    imgurl: HttpUrl = Field(...,
                            description="The thumbnail or representative website image URL")

    class Settings:
        # This targets the exact collection name inside MongoDB
        name = "root_cause_items"

        # Allows you to pass either camelCase (from Mongo) or snake_case parameters dynamically
        populate_by_name = True
