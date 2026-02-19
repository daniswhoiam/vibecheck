"""Seed the Entity table with curated AI models and tools.

This script populates the entities table with the 10 curated entities
defined in utils/constants.py. It handles duplicates gracefully by
skipping entities that already exist.

Usage:
    python scripts/seed_entities.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.session import AsyncSessionLocal
from db.models import Entity
from utils.constants import CURATED_ENTITIES


async def seed_entities():
    """Seed the Entity table with curated entities.

    Inserts all curated entities from constants.py, skipping any that
    already exist in the database to avoid duplicate key errors.

    Returns:
        int: Number of entities successfully added to the database.
    """
    print("Starting entity seeding...")

    async with AsyncSessionLocal() as session:
        try:
            # Fetch existing entities to avoid duplicates
            result = await session.execute(select(Entity.name))
            existing_names = set(result.scalars().all())

            print(f"Found {len(existing_names)} existing entities in database")

            # Count how many we'll add
            entities_to_add = [
                entity
                for entity in CURATED_ENTITIES
                if entity["name"] not in existing_names
            ]

            if not entities_to_add:
                print("All curated entities already exist. Nothing to add.")
                print("\nCurrent entities:")
                for name in sorted(existing_names):
                    print(f"  - {name}")
                return 0

            print(f"Adding {len(entities_to_add)} new entities:")

            # Create and add new entities
            added_entities = []
            for entity_data in entities_to_add:
                entity = Entity(
                    name=entity_data["name"],
                    category=entity_data["category"]
                )
                session.add(entity)
                added_entities.append(entity)
                print(f"  + {entity_data['name']} ({entity_data['category']})")

            # Commit the transaction
            await session.commit()
            print(f"\n✓ Successfully seeded {len(entities_to_add)} entities")

            # Verify the final count
            result = await session.execute(select(Entity))
            total_count = len(result.scalars().all())
            print(f"  Total entities in database: {total_count}")

            return len(entities_to_add)

        except Exception as e:
            await session.rollback()
            print(f"\n✗ Error seeding entities: {e}")
            raise


async def list_entities():
    """List all entities currently in the database."""
    print("\nCurrent entities in database:")
    print("-" * 50)

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(Entity).order_by(Entity.category, Entity.name)
            )
            entities = result.scalars().all()

            if not entities:
                print("No entities found.")
                return

            current_category = None
            for entity in entities:
                if entity.category != current_category:
                    current_category = entity.category
                    print(f"\n{current_category.title()}s:")
                print(f"  [{entity.id}] {entity.name}")

        except Exception as e:
            print(f"Error listing entities: {e}")
            raise


async def main():
    """Main function that combines seeding and listing."""
    print("=" * 50)
    print("VibeCheck Entity Seeding Script")
    print("=" * 50)

    try:
        await seed_entities()
        await list_entities()
        print("\n" + "=" * 50)
        print("Entity seeding complete!")
        print("=" * 50)
    except KeyboardInterrupt:
        print("\n\nSeeding interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nSeeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
