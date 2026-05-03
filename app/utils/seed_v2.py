"""Seed default roles and permissions for V2 features"""
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.models import AdminRole, RolePermission, UserRole


async def seed_default_roles(db: AsyncSession):
    """Create default admin roles and permissions"""

    roles_config = {
        "Super Admin": {
            "role_type": UserRole.SUPER_ADMIN,
            "description": "Accès complet au système",
            "permissions": [
                "commerce.create", "commerce.edit", "commerce.delete", "commerce.approve",
                "user.ban", "user.manage", "admin.logs", "admin.roles",
                "finance.manage", "advertising.manage", "events.manage",
                "surveyor.manage", "category.manage"
            ]
        },
        "Admin": {
            "role_type": UserRole.ADMIN,
            "description": "Gestion générale du système",
            "permissions": [
                "commerce.approve", "commerce.edit", "user.manage", "admin.logs",
                "advertising.manage", "surveyor.manage"
            ]
        },
        "Admin Régional": {
            "role_type": UserRole.REGIONAL_ADMIN,
            "description": "Gestion d'une région spécifique",
            "permissions": [
                "commerce.approve", "surveyor.manage", "user.manage"
            ]
        },
        "Superviseur": {
            "role_type": UserRole.SUPERVISOR,
            "description": "Supervision des enquêtes terrain",
            "permissions": [
                "surveyor.manage", "commerce.verify", "admin.logs"
            ]
        },
        "Modérateur": {
            "role_type": UserRole.MODERATOR,
            "description": "Modération du contenu et des avis",
            "permissions": [
                "commerce.edit", "reviews.manage"
            ]
        },
        "Support Client": {
            "role_type": UserRole.SUPPORT,
            "description": "Support client et gestion des tickets",
            "permissions": [
                "tickets.manage", "user.support"
            ]
        },
        "Finance": {
            "role_type": UserRole.FINANCE,
            "description": "Gestion financière et des revenus",
            "permissions": [
                "finance.manage", "subscriptions.view", "advertising.analytics"
            ]
        },
        "Marketing": {
            "role_type": UserRole.MARKETING,
            "description": "Gestion marketing et promotions",
            "permissions": [
                "advertising.manage", "events.manage", "promotions.manage", "category.manage"
            ]
        },
        "Gestionnaire Publicité": {
            "role_type": UserRole.AD_MANAGER,
            "description": "Gestion des publicités et des sponsors",
            "permissions": [
                "advertising.manage", "advertising.analytics"
            ]
        },
        "Gestionnaire Événements": {
            "role_type": UserRole.EVENT_MANAGER,
            "description": "Gestion des événements",
            "permissions": [
                "events.manage", "events.publish"
            ]
        },
    }

    for role_name, config in roles_config.items():
        # Check if role exists
        existing = await db.execute(
            select(AdminRole).where(AdminRole.name == role_name)
        )
        if existing.scalar():
            continue

        role = AdminRole(
            name=role_name,
            role_type=config["role_type"],
            description=config["description"],
            is_custom=False
        )
        db.add(role)
        await db.flush()

        # Add permissions
        for perm in config["permissions"]:
            permission = RolePermission(
                admin_role_id=role.id,
                permission=perm,
                is_granted=True
            )
            db.add(permission)

    await db.commit()
    print("✅ Default roles seeded successfully!")


from sqlalchemy import select
