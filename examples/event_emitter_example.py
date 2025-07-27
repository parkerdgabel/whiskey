"""Example demonstrating the @emits decorator for automatic event emission."""

import asyncio
from typing import Dict
from whiskey import Application, inject


# Mock services
class Database:
    """Mock database."""
    def __init__(self):
        self.users = {}
        self.next_id = 1
        
    async def create_user(self, name: str, email: str) -> Dict:
        user = {
            "id": self.next_id,
            "name": name,
            "email": email
        }
        self.users[self.next_id] = user
        self.next_id += 1
        return user
        
    async def update_user(self, user_id: int, **updates) -> Dict:
        user = self.users[user_id]
        user.update(updates)
        return user


class EmailService:
    """Mock email service."""
    async def send_welcome(self, user: Dict):
        print(f"📧 Welcome email sent to {user['email']}")
        
    async def send_update_notification(self, user: Dict):
        print(f"📧 Update notification sent to {user['email']}")


class AuditLogger:
    """Mock audit logger."""
    def __init__(self):
        self.events = []
        
    async def log(self, event_type: str, data: Dict):
        self.events.append({"type": event_type, "data": data})
        print(f"📝 Audit: {event_type} - {data}")


# Create application
app = Application()

# Register services
app.container.register(Database, scope="singleton")
app.container.register(EmailService, scope="singleton")
app.container.register(AuditLogger, scope="singleton")


# Service layer with @emits decorator
class UserService:
    """User service that automatically emits events."""
    
    def __init__(self, db: Database):
        self.db = db
    
    @app.emits("user.created")
    async def create_user(self, name: str, email: str) -> Dict:
        """Create a user and automatically emit user.created event."""
        print(f"\n🔧 Creating user: {name}")
        user = await self.db.create_user(name, email)
        return user  # This return value is automatically emitted as "user.created"
    
    @app.emits("user.updated")
    async def update_user(self, user_id: int, **updates) -> Dict:
        """Update a user and automatically emit user.updated event."""
        print(f"\n🔧 Updating user {user_id}: {updates}")
        user = await self.db.update_user(user_id, **updates)
        return user  # This return value is automatically emitted as "user.updated"
    
    @app.emits("user.batch_created")
    async def create_users_batch(self, users_data: list) -> Dict:
        """Create multiple users and emit a batch event."""
        print(f"\n🔧 Creating {len(users_data)} users in batch")
        created_users = []
        for data in users_data:
            user = await self.db.create_user(data["name"], data["email"])
            created_users.append(user)
        return {
            "count": len(created_users),
            "users": created_users
        }  # Emitted as "user.batch_created"


# Register the service
app.component(UserService)


# Event handlers
@app.on("user.created")
@inject
async def send_welcome_email(user: Dict, email_service: EmailService):
    """Send welcome email when user is created."""
    await email_service.send_welcome(user)


@app.on("user.updated") 
@inject
async def send_update_notification(user: Dict, email_service: EmailService):
    """Send notification when user is updated."""
    await email_service.send_update_notification(user)


@app.on("user.*")  # Wildcard - catches all user events
@inject
async def audit_user_events(data: Dict, logger: AuditLogger):
    """Log all user-related events for audit."""
    # Determine event type from the handler context
    event_type = "user.event"  # In real app, would get actual event name
    await logger.log(event_type, data)


@app.on("user.batch_created")
async def handle_batch_creation(data: Dict):
    """Handle batch user creation."""
    print(f"📊 Batch created: {data['count']} users")
    for user in data['users']:
        print(f"   - {user['name']} ({user['email']})")


# Example with sync function
@app.emits("config.loaded")
def load_config() -> Dict:
    """Sync function that emits an event."""
    print("\n⚙️  Loading configuration...")
    config = {"debug": True, "version": "1.0.0"}
    return config  # Emitted as "config.loaded"


@app.on("config.loaded")
async def on_config_loaded(config: Dict):
    print(f"✅ Config loaded: {config}")


# Main application
@app.main
@inject
async def main(user_service: UserService, logger: AuditLogger):
    """Main function demonstrating @emits decorator."""
    print("=" * 50)
    print("Whiskey @emits Decorator Example")
    print("=" * 50)
    
    # Create some users - events are automatically emitted
    alice = await user_service.create_user("Alice", "alice@example.com")
    bob = await user_service.create_user("Bob", "bob@example.com")
    
    # Update a user - event automatically emitted
    await user_service.update_user(alice["id"], name="Alice Smith")
    
    # Batch creation
    batch_users = [
        {"name": "Charlie", "email": "charlie@example.com"},
        {"name": "Diana", "email": "diana@example.com"},
        {"name": "Eve", "email": "eve@example.com"}
    ]
    await user_service.create_users_batch(batch_users)
    
    # Load config (sync function)
    load_config()
    
    # Give async events time to process
    await asyncio.sleep(0.1)
    
    # Show audit log
    print(f"\n📋 Total events logged: {len(logger.events)}")


if __name__ == "__main__":
    app.run()