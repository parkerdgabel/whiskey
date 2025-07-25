"""Simple example of Whiskey's Pythonic DI."""

import asyncio
from whiskey import Container, inject, provide, singleton


# Services
@singleton
class Database:
    def __init__(self):
        self.connection = "Connected to DB"
        print("Database initialized")
        
    async def query(self, sql: str) -> list:
        print(f"Executing: {sql}")
        return [{"id": 1, "name": "Alice"}]


@provide
class UserService:
    def __init__(self, db: Database):
        self.db = db
        print("UserService initialized")
        
    async def get_user(self, user_id: int):
        users = await self.db.query(f"SELECT * FROM users WHERE id = {user_id}")
        return users[0] if users else None


# Using @inject decorator
@inject
async def process_user(user_id: int, user_service: UserService):
    """Function with automatic dependency injection."""
    user = await user_service.get_user(user_id)
    if user:
        print(f"Processing user: {user['name']}")
        return user
    return None


async def main():
    # Example 1: Using the default container
    print("=== Using Default Container ===")
    result = await process_user(1)
    print(f"Result: {result}\n")
    
    # Example 2: Using explicit container
    print("=== Using Explicit Container ===")
    container = Container()
    
    # Register services - dict-like interface
    container[Database] = Database  # Class will be instantiated
    container[UserService] = UserService  # Dependencies auto-resolved
    
    # Resolve and use
    user_service = await container.resolve(UserService)
    user = await user_service.get_user(1)
    print(f"Found user: {user}\n")
    
    # Example 3: Factory functions
    print("=== Using Factories ===")
    container = Container()
    
    def create_database() -> Database:
        db = Database()
        db.connection = "Custom connection"
        return db
    
    container[Database] = create_database  # Factory function
    container[UserService] = UserService
    
    service = await container.resolve(UserService)
    print(f"DB connection: {service.db.connection}")


if __name__ == "__main__":
    asyncio.run(main())