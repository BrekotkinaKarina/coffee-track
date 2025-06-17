import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Literal, Optional
from enum import Enum
from datetime import datetime

class CoffeeSize(str, Enum):
    SMALL = 'small'
    MEDIUM = 'medium'
    LARGE = 'large'

class CoffeeType(str, Enum):
    LATTE = 'latte'
    AMERICANO = 'americano'
    CAPPUCCINO = 'cappuccino'
    ESPRESSO = 'espresso'

class OrderStatus(str, Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    READY = 'ready'
    CANCELLED = 'cancelled'

class IngredientType(str, Enum):
    MILK = "молоко"
    WATER = "вода"
    COFFEE_BEANS = "кофе"
    FOAM = "пенка"

COFFEE_RECIPES = {
    CoffeeType.LATTE: {
        IngredientType.MILK: 200,
        IngredientType.COFFEE_BEANS: 18,
        IngredientType.FOAM: 50
    },
    CoffeeType.AMERICANO: {
        IngredientType.WATER: 150,
        IngredientType.COFFEE_BEANS: 15
    },
    CoffeeType.CAPPUCCINO: {
        IngredientType.MILK: 100,
        IngredientType.COFFEE_BEANS: 18,
        IngredientType.FOAM: 100
    },
    CoffeeType.ESPRESSO: {
        IngredientType.COFFEE_BEANS: 7,
        IngredientType.WATER: 30
    }
}

class CoffeeBase(BaseModel):
    coffee_type: CoffeeType
    size: CoffeeSize = CoffeeSize.MEDIUM
    
    @property
    def ingredients(self) -> Dict[IngredientType, float]:
        size_multiplier = {
            CoffeeSize.SMALL: 0.8,
            CoffeeSize.MEDIUM: 1.0,
            CoffeeSize.LARGE: 1.2
        }[self.size]
        
        return {
            ingr: amount * size_multiplier
            for ingr, amount in COFFEE_RECIPES[self.coffee_type].items()
        }

    @property
    def name(self) -> str:
        names = {
            CoffeeType.LATTE: "Латте",
            CoffeeType.AMERICANO: "Американо",
            CoffeeType.CAPPUCCINO: "Капучино",
            CoffeeType.ESPRESSO: "Эспрессо"
        }
        return names[self.coffee_type]

    preparation_time: int = Field(60, ge=10) 

class OrderItem(BaseModel):
    coffee_type: CoffeeType  
    size: CoffeeSize
    quantity: int = Field(1, gt=0, le=10)
    
    def get_ingredients(self) -> Dict[IngredientType, float]:
        base = CoffeeBase(coffee_type=self.coffee_type, size=self.size)
        return {k: v * self.quantity for k, v in base.ingredients.items()}
    
class OrderCreate(BaseModel):
    customer_name: str = Field(..., min_length=2, max_length=50)
    items: List[OrderItem] = Field(..., min_items=1)

class OrderResponse(OrderCreate):
    id: UUID = Field(default_factory=uuid4)
    status: OrderStatus = OrderStatus.PENDING
    ingredients_used: Dict[IngredientType, float]
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    estimated_ready_time: Optional[int] = None




