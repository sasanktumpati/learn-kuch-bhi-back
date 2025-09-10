from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.db.base import get_session
from app.core.db.schemas.auth import User
from app.core.db.schemas.user_profile import UserProfile
from app.modules.auth import fastapi_users
from .schemas import UserProfileCreate, UserProfileUpdate, UserProfileRead


router = APIRouter()


async def get_current_user(user: User = Depends(fastapi_users.current_user())) -> User:
    return user


async def get_or_create_profile(
    session: AsyncSession,
    user_id: int,
    profile_data: UserProfileCreate | None = None,
) -> UserProfile:
    """Get existing profile or create a new one with default values"""
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()
    
    if not profile:
        # Create profile with provided data or defaults
        profile_dict = profile_data.model_dump(exclude_unset=True) if profile_data else {}
        
        # Set default values for required fields if not provided
        if 'first_name' not in profile_dict:
            profile_dict['first_name'] = 'User'
        if 'last_name' not in profile_dict:
            profile_dict['last_name'] = f'{user_id}'
        
        profile = UserProfile(
            user_id=user_id,
            **profile_dict
        )
        
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    
    return profile


@router.post(
    f"/{settings.app.version}/profile",
    response_model=UserProfileRead,
    status_code=status.HTTP_200_OK,
    tags=["user_profile"],
)
async def create_or_update_profile(
    profile_data: UserProfileCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create or update user profile"""
    result = await session.execute(
        select(UserProfile).where(UserProfile.user_id == current_user.id)
    )
    existing_profile = result.scalar_one_or_none()
    
    if existing_profile:
        # Update existing profile
        update_data = profile_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing_profile, field, value)
        
        await session.commit()
        await session.refresh(existing_profile)
        return UserProfileRead.model_validate(existing_profile)
    else:
        # Create new profile
        profile = await get_or_create_profile(session, current_user.id, profile_data)
        return UserProfileRead.model_validate(profile)


@router.get(
    f"/{settings.app.version}/profile",
    response_model=UserProfileRead,
    tags=["user_profile"],
)
async def get_profile(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get user profile, auto-create if doesn't exist"""
    profile = await get_or_create_profile(session, current_user.id)
    return UserProfileRead.model_validate(profile)


@router.put(
    f"/{settings.app.version}/profile",
    response_model=UserProfileRead,
    tags=["user_profile"],
)
async def update_profile(
    profile_data: UserProfileUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Update user profile, auto-create if doesn't exist"""
    profile = await get_or_create_profile(session, current_user.id)

    # Update profile with provided data
    update_data = profile_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await session.commit()
    await session.refresh(profile)

    return UserProfileRead.model_validate(profile)


@router.get(
    f"/{settings.app.version}/profile/me",
    response_model=UserProfileRead,
    tags=["user_profile"],
)
async def get_my_profile(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Alias for get_profile - get current user's profile"""
    return await get_profile(session, current_user)
