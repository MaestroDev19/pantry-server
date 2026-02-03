from typing import List, Optional

from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID
from enum import Enum

# -------------------------
# Enum definitions
# -------------------------

class DietaryTag(str, Enum):
    """
    Dietary restriction tags for recipes, to filter or tag recipes according to specific diets or allergies.
    """
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    GLUTEN_FREE = "gluten_free"
    DAIRY_FREE = "dairy_free"
    NUT_FREE = "nut_free"
    LOW_CARB = "low_carb"
    KETO = "keto"
    PALEO = "paleo"
    HALAL = "halal"
    KOSHER = "kosher"

class Difficulty(str, Enum):
    """
    Levels of recipe difficulty to help users gauge required cooking proficiency.
    """
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"

class RecipeMode(str, Enum):
    """
    Represents how to source pantry items for recipe generation.
    - PERSONAL: Only items owned by the requesting user.
    - HOUSEHOLD: Includes all items in the shared household.
    """
    PERSONAL = "personal"    # Only use the user's own pantry items
    HOUSEHOLD = "household"  # Include all household pantry items

# -------------------------
# Ingredient and Step Models
# -------------------------

class RecipeIngredient(BaseModel):
    """
    Represents a single ingredient used in a recipe.
    
    Fields:
        - name: The name of the ingredient (e.g., "Carrots"). Required, 1-100 chars.
        - quantity: The ingredient quantity as a human-friendly string (e.g., "2 cups", "500g").
        - unit: Optional unit as a string (e.g., "g", "cups"). For display or matching.
        - have: Whether the user (household) currently has this ingredient available.
        - owner: Which member's pantry supplied the ingredient ("YOU", "Sarah", etc.). None if needs buying.
        - pantry_item_id: UUID of the corresponding pantry item, if available.
    """
    name: str = Field(..., min_length=1, max_length=100)
    quantity: str = Field(..., max_length=50)
    unit: Optional[str] = Field(None, max_length=20)
    have: bool = False
    owner: Optional[str] = None
    pantry_item_id: Optional[UUID] = None

    @field_validator("name")
    def validate_name(cls, value: str) -> str:
        """
        Ensure ingredient names are lowercase and stripped of whitespace for internal consistency.
        """
        return value.strip().lower()

class RecipeStep(BaseModel):
    """
    Represents a single step/instruction in a recipe.
    
    Fields:
        - step_number: Sequential number for step ordering. Must be >=1.
        - instruction: The full step instruction text (10-500 chars).
    """
    step_number: int = Field(..., ge=1)
    instruction: str = Field(..., min_length=10, max_length=500)

# -------------------------
# Base Recipe Structure
# -------------------------

class RecipeBase(BaseModel):
    """
    Base model defining all the core attributes for a recipe.
    
    Fields:
        - title: The recipe's title (display name). Required.
        - description: Optional, rich text or summary of the recipe.
        - ingredients: List of RecipeIngredient objects (at least 1).
        - instructions: List of instructions (strings, can be detailed steps).
        - prep_time: Preparation time in minutes (0-480).
        - cook_time: Cooking time in minutes (0-480).
        - servings: Number of servings (1-50).
        - difficulty: Optional difficulty level ("easy", "medium", "hard").
        - cuisine: Optional, describes type/culture (e.g. "Italian").
        - dietary_tags: DietaryTag enums for user filtering (e.g. vegan, nut_free).
    """
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=500)
    ingredients: List[RecipeIngredient] = Field(..., min_items=1)
    instructions: List[str] = Field(..., min_items=1)  # Each item is a string instruction, optionally use RecipeStep.
    prep_time: int = Field(..., ge=0, le=480)
    cook_time: int = Field(..., ge=0, le=480)
    servings: int = Field(..., ge=1, le=50)
    difficulty: Optional[Difficulty] = Difficulty.MEDIUM
    cuisine: Optional[str] = Field(None, max_length=50)
    dietary_tags: List[DietaryTag] = Field(default_factory=list)

    @field_validator("title")
    def validate_title(cls, value: str) -> str:
        """
        Cleanup and standardize recipe titles to title case.
        """
        return value.strip().title()

    @property
    def total_time(self) -> int:
        """
        Computed property for total recipe time in minutes (prep + cook).
        """
        return self.prep_time + self.cook_time

# -------------------------
# Subclasses & Responses
# -------------------------

class RecipeCreate(RecipeBase):
    """
    Data required to create a new recipe entry.
    Inherits all attributes from RecipeBase.
    """
    pass

class RecipeResponse(RecipeBase):
    """
    Complete model for returning recipe metadata via API, including DB fields and computed fields.
    
    Fields:
        - id: Unique UUID of the recipe in DB.
        - external_id: Optional, for 3rd-party recipes.
        - image_url: Optional image (URL or link).
        - source_url: Link to source if copied.
        - created_at: When recipe was created.
        - ingredients_available: Number of required ingredients currently in the user's pantry/household.
        - ingredients_needed: Number of ingredients missing/not found in pantry.
        - can_make: True if all required ingredients are available.
    """
    id: UUID
    external_id: Optional[str] = None
    image_url: Optional[str] = None
    source_url: Optional[str] = None
    created_at: datetime

    # Computed fields reported by the API/UI logic,
    # not used for recipe creation
    ingredients_available: int = 0     # Count of available ingredients in user's pantry/household
    ingredients_needed: int = 0        # Count of ingredients not available/missing
    can_make: bool = False             # True if ingredients_needed == 0

    class Config:
        from_attributes = True         # Enables ORM serialization (e.g., SQLAlchemy obj → model)
        use_enum_values = True         # Output enum values (str) instead of enum objects

# -------------------------
# Recipe Generation Request/Response
# -------------------------

class RecipeGenerateRequest(BaseModel):
    """
    Request payload for generating new recipes via AI or algorithm.
    
    Fields:
        - mode: Whether to use PERSONAL or HOUSEHOLD inventory (see RecipeMode).
        - dietary_preferences: Which dietary tags must be applied to generated recipes.
        - max_items_to_use: Max number of pantry items to use in each recipe (5-30, default 15).
        - cuisine: Optionally specify desired cuisine for recipe generation.
        - max_prep_time: Limit generated recipes to those with prep time ≤ this (5-120 minutes).
        - difficulty: If set, restrict generated recipes to given difficulty.
        - num_recipes: Number of recipes to return (1-5, default 3).
    """
    mode: RecipeMode = RecipeMode.PERSONAL
    dietary_preferences: List[DietaryTag] = Field(default_factory=list)
    max_items_to_use: int = Field(default=15, ge=5, le=30)
    cuisine: Optional[str] = Field(None, max_length=50)
    max_prep_time: Optional[int] = Field(None, ge=5, le=120)
    difficulty: Optional[Difficulty] = None
    num_recipes: int = Field(default=3, ge=1, le=5)

class RecipeGenerateResponse(BaseModel):
    """
    Response payload after generating recipes.
    
    Fields:
        - recipes: List of generated RecipeResponse objects.
        - mode: Which mode was used (PERSONAL or HOUSEHOLD).
        - pantry_items_used: Total number of pantry items used for generation.
        - generation_time: Time taken in seconds for the generation process.
        - tokens_used: (Optional) Number of AI/LLM tokens used if relevant.
    """
    recipes: List[RecipeResponse]
    mode: RecipeMode
    pantry_items_used: int
    generation_time: float  # seconds to generate
    tokens_used: Optional[int] = None

# -------------------------
# Marking Ingredients Used
# -------------------------

class RecipeUseIngredientsRequest(BaseModel):
    """
    Request payload to mark specified ingredients as 'used', to update pantry after cooking.
    
    Fields:
        - recipe_id: UUID of the relevant recipe.
        - ingredient_indices: List of index positions in the recipe's ingredient list to mark as used.
    """
    recipe_id: UUID
    ingredient_indices: List[int] = Field(..., min_items=1)

class RecipeUseIngredientsResponse(BaseModel):
    """
    Response after marking ingredients as 'used', indicating what pantry items were depleted/removed.
    
    Fields:
        - updated_items: UUIDs for pantry items that were updated (quantity reduced but not depleted).
        - deleted_items: UUIDs for pantry items that were removed from pantry (quantity zeroed/depleted).
        - message: User-friendly explanation of the action/results.
    """
    updated_items: List[UUID] = Field(default_factory=list)
    deleted_items: List[UUID] = Field(default_factory=list)
    message: str

# -------------------------
# Recipe Search Model
# -------------------------

class RecipeSearchRequest(BaseModel):
    """
    Request payload for searching (filtering) recipes by user criteria.
    
    Fields:
        - query: User search string (name, keyword, etc.). Required.
        - dietary_preferences: List of dietary tags to filter by.
        - max_prep_time: (Optional) Return recipes ≤ this prep time (minutes).
        - difficulty: (Optional) Only return recipes of specified difficulty.
        - limit: Maximum number of recipes to return (1-50, default 10).
    """
    query: str = Field(..., min_length=1, max_length=200)
    dietary_preferences: List[DietaryTag] = Field(default_factory=list)
    max_prep_time: Optional[int] = Field(None, ge=5, le=120)
    difficulty: Optional[Difficulty] = None
    limit: int = Field(default=10, ge=1, le=50)