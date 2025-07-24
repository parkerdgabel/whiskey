"""Example demonstrating syntactic sugar for the Container class."""

import asyncio
from whiskey import Container, singleton, provide


@singleton
class Database:
    def __init__(self):
        self.connected = True
        self.data = {"users": [], "products": []}


@provide
class UserService:
    def __init__(self, db: Database):
        self.db = db
    
    def add_user(self, name: str):
        self.db.data["users"].append(name)
        return f"Added user: {name}"


@provide  
class ProductService:
    def __init__(self, db: Database):
        self.db = db
    
    def add_product(self, name: str):
        self.db.data["products"].append(name)
        return f"Added product: {name}"


def demo_syntactic_sugar():
    """Demonstrate various syntactic sugar features."""
    container = Container()
    
    # Register services
    container.register_singleton(Database, Database)
    container.register(UserService, UserService)
    container.register(ProductService, ProductService)
    
    print("=== Syntactic Sugar Demo ===\n")
    
    # 1. Dict-like access with []
    print("1. Dict-like access:")
    db = container[Database]
    print(f"   container[Database] = {db}")
    print(f"   Database connected: {db.connected}\n")
    
    # 2. Using get() with default
    print("2. Using get() with default:")
    user_service = container.get(UserService)
    print(f"   container.get(UserService) = {user_service}")
    
    # Non-existent service returns None
    missing = container.get(str, default="not found")  
    print(f"   container.get(str, 'not found') = {missing}\n")
    
    # 3. Using 'in' operator
    print("3. Using 'in' operator:")
    print(f"   Database in container = {Database in container}")
    print(f"   str in container = {str in container}\n")
    
    # 4. Named services with tuple
    container.register(UserService, UserService, name="special")
    print("4. Named services:")
    print(f"   (UserService, 'special') in container = {(UserService, 'special') in container}")
    print(f"   (UserService, 'other') in container = {(UserService, 'other') in container}\n")
    
    # 5. Context manager
    print("5. Context manager:")
    with Container() as temp_container:
        temp_container.register_singleton(Database, Database)
        print(f"   Services in temp container: {len(temp_container)}")
    print("   Container disposed after context exit\n")
    
    # 6. Length and iteration
    print("6. Length and iteration:")
    print(f"   len(container) = {len(container)}")
    print("   Service types registered:")
    for key in container:
        print(f"     - {key}")
    print()
    
    # 7. Dict-like methods
    print("7. Dict-like methods:")
    print(f"   container.keys() count = {len(list(container.keys()))}")
    print(f"   container.values() count = {len(list(container.values()))}")
    print("   First few items:")
    for i, (key, desc) in enumerate(container.items()):
        if i >= 3:
            break
        print(f"     {key} -> {desc.scope}")


async def demo_async_sugar():
    """Demonstrate async syntactic sugar."""
    print("\n=== Async Syntactic Sugar ===\n")
    
    # Async context manager
    async with Container() as container:
        container.register_singleton(Database, Database)
        container.register(UserService, UserService)
        
        # Using aget()
        db = await container.aget(Database)
        print(f"1. await container.aget(Database) = {db}")
        
        # aget with default for missing service
        missing = await container.aget(str, default="not found")
        print(f"2. await container.aget(str, 'not found') = {missing}")
        
        # Regular async resolve still works
        user_service = await container.resolve(UserService)
        result = user_service.add_user("Alice")
        print(f"3. {result}")
    
    print("4. Container disposed after async context exit")


def main():
    """Run all demos."""
    demo_syntactic_sugar()
    asyncio.run(demo_async_sugar())


if __name__ == "__main__":
    main()