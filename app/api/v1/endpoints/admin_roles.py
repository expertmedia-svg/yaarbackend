from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc
from typing import List, Optional
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    User, UserRole, AdminRole, RolePermission, AuditLog
)
from app.schemas.schemas import (
    AdminRoleCreate, AdminRoleResponse, RolePermissionResponse,
    AuditLogResponse, PaginationResponse
)

router = APIRouter(prefix="/admin", tags=["Admin Management"])


# ── Role Management ───────────────────────────────────────────────────────────

@router.post("/roles", response_model=AdminRoleResponse)
async def create_role(
    data: AdminRoleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new admin role"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admin can create roles")

    existing = await db.execute(
        select(AdminRole).where(AdminRole.name == data.name)
    )
    if existing.scalar():
        raise HTTPException(status_code=400, detail="Role name already exists")

    role = AdminRole(
        name=data.name,
        role_type=data.role_type,
        description=data.description,
        is_custom=True
    )
    db.add(role)
    await db.flush()

    # Add permissions
    for perm_data in data.permissions:
        permission = RolePermission(
            admin_role_id=role.id,
            permission=perm_data.permission,
            is_granted=perm_data.is_granted
        )
        db.add(permission)

    await db.commit()
    await db.refresh(role)
    return role


@router.get("/roles", response_model=List[AdminRoleResponse])
async def list_roles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    include_custom: bool = True
):
    """List all admin roles"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized")

    query = select(AdminRole)
    if not include_custom:
        query = query.where(AdminRole.is_custom == False)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/roles/{role_id}", response_model=AdminRoleResponse)
async def get_role(
    role_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get role details"""
    result = await db.execute(
        select(AdminRole).where(AdminRole.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.put("/roles/{role_id}", response_model=AdminRoleResponse)
async def update_role(
    role_id: str,
    data: AdminRoleCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update admin role"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admin can update roles")

    result = await db.execute(
        select(AdminRole).where(AdminRole.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    role.name = data.name
    role.description = data.description
    role.role_type = data.role_type

    # Delete existing permissions
    await db.execute(
        select(RolePermission).where(RolePermission.admin_role_id == role_id)
    )

    # Add new permissions
    for perm_data in data.permissions:
        permission = RolePermission(
            admin_role_id=role.id,
            permission=perm_data.permission,
            is_granted=perm_data.is_granted
        )
        db.add(permission)

    await db.commit()
    await db.refresh(role)
    return role


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete admin role"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Only super admin can delete roles")

    result = await db.execute(
        select(AdminRole).where(AdminRole.id == role_id)
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if not role.is_custom:
        raise HTTPException(status_code=400, detail="Cannot delete default roles")

    await db.delete(role)
    await db.commit()
    return {"status": "deleted"}


# ── Permission Management ──────────────────────────────────────────────────────

@router.post("/roles/{role_id}/permissions", response_model=RolePermissionResponse)
async def add_permission(
    role_id: str,
    permission: str,
    is_granted: bool = True,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Add permission to role"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(AdminRole).where(AdminRole.id == role_id)
    )
    if not result.scalar():
        raise HTTPException(status_code=404, detail="Role not found")

    perm = RolePermission(
        admin_role_id=role_id,
        permission=permission,
        is_granted=is_granted
    )
    db.add(perm)
    await db.commit()
    await db.refresh(perm)
    return perm


@router.delete("/permissions/{permission_id}")
async def remove_permission(
    permission_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Remove permission from role"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(RolePermission).where(RolePermission.id == permission_id)
    )
    perm = result.scalar_one_or_none()
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")

    await db.delete(perm)
    await db.commit()
    return {"status": "deleted"}


# ── User Role Assignment ───────────────────────────────────────────────────────

@router.post("/users/{user_id}/roles/{role_type}")
async def assign_role(
    user_id: str,
    role_type: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Assign admin role to user"""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="Not authorized")

    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.role = role_type
    user.is_admin = role_type in ["admin", "super_admin"]
    await db.commit()

    # Log action
    audit = AuditLog(
        admin_id=current_user.id,
        action="assign_role",
        resource_type="user",
        resource_id=user_id,
        changes={"role": role_type},
        status="success"
    )
    db.add(audit)
    await db.commit()

    return {"user_id": user_id, "role": role_type}


# ── Audit Logs ─────────────────────────────────────────────────────────────────

@router.get("/audit-logs", response_model=PaginationResponse)
async def list_audit_logs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    admin_id: Optional[str] = None
):
    """List audit logs"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized")

    query = select(AuditLog)
    if action:
        query = query.where(AuditLog.action == action)
    if resource_type:
        query = query.where(AuditLog.resource_type == resource_type)
    if admin_id:
        query = query.where(AuditLog.admin_id == admin_id)

    result = await db.execute(query)
    total = len(result.scalars().all())

    result = await db.execute(
        query.order_by(desc(AuditLog.created_at))
        .offset((page - 1) * limit)
        .limit(limit)
    )
    items = result.scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit
    }


@router.get("/audit-logs/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get audit log details"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized")

    result = await db.execute(
        select(AuditLog).where(AuditLog.id == log_id)
    )
    log = result.scalar_one_or_none()
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    return log


@router.get("/stats")
async def get_admin_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get admin panel statistics"""
    if current_user.role not in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Not authorized")

    from app.models.models import User as UserModel, Commerce, Subscription

    users_result = await db.execute(select(UserModel))
    total_users = len(users_result.scalars().all())

    premium_result = await db.execute(
        select(UserModel).where(UserModel.is_premium == True)
    )
    premium_users = len(premium_result.scalars().all())

    commerces_result = await db.execute(select(Commerce))
    total_commerces = len(commerces_result.scalars().all())

    pending_result = await db.execute(
        select(Commerce).where(Commerce.status == "pending")
    )
    pending_commerces = len(pending_result.scalars().all())

    return {
        "total_users": total_users,
        "premium_users": premium_users,
        "total_commerces": total_commerces,
        "pending_commerces": pending_commerces,
        "timestamp": datetime.utcnow()
    }
