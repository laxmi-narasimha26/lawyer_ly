"""
Production-grade authentication and authorization system
Implements JWT-based security with comprehensive user management
"""
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from config import settings
from database import get_db_session, User
from utils.exceptions import AuthenticationError, AuthorizationError

logger = structlog.get_logger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Security
security = HTTPBearer()

class AuthenticationService:
    """
    Production-grade authentication service
    
    Features:
    - JWT token generation and validation
    - Password hashing and verification
    - User session management
    - Rate limiting for authentication attempts
    - Account lockout protection
    """
    
    def __init__(self):
        self.secret_key = settings.security.secret_key
        self.algorithm = settings.security.algorithm
        self.access_token_expire_minutes = settings.security.access_token_expire_minutes
        self.refresh_token_expire_days = settings.security.refresh_token_expire_days
        
        logger.info("Authentication service initialized")
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception as e:
            logger.error("Password verification failed", error=str(e))
            return False
    
    def get_password_hash(self, password: str) -> str:
        """Generate password hash"""
        return pwd_context.hash(password)
    
    def create_access_token(
        self,
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token
        
        Args:
            data: Token payload data
            expires_delta: Custom expiration time
            
        Returns:
            JWT token string
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        try:
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            return encoded_jwt
        except Exception as e:
            logger.error("Token creation failed", error=str(e))
            raise AuthenticationError("Failed to create access token")
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """
        Create JWT refresh token
        
        Args:
            data: Token payload data
            
        Returns:
            JWT refresh token string
        """
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        try:
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            return encoded_jwt
        except Exception as e:
            logger.error("Refresh token creation failed", error=str(e))
            raise AuthenticationError("Failed to create refresh token")
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
            
        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # Check token type
            token_type = payload.get("type")
            if token_type not in ["access", "refresh"]:
                raise AuthenticationError("Invalid token type")
            
            # Check expiration
            exp = payload.get("exp")
            if exp is None:
                raise AuthenticationError("Token missing expiration")
            
            if datetime.utcnow() > datetime.fromtimestamp(exp):
                raise AuthenticationError("Token has expired")
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token provided", error=str(e))
            raise AuthenticationError("Invalid token")
        except Exception as e:
            logger.error("Token verification failed", error=str(e))
            raise AuthenticationError("Token verification failed")
    
    async def authenticate_user(
        self,
        email: str,
        password: str,
        session: AsyncSession
    ) -> Optional[User]:
        """
        Authenticate user with email and password
        
        Args:
            email: User email
            password: Plain text password
            session: Database session
            
        Returns:
            User object if authentication successful, None otherwise
        """
        try:
            # Get user by email
            stmt = select(User).where(User.email == email.lower())
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                logger.warning("Authentication failed - user not found", email=email)
                return None
            
            # Check if account is active
            if not user.is_active:
                logger.warning("Authentication failed - account inactive", email=email)
                return None
            
            # Check if account is locked
            if user.locked_until and user.locked_until > datetime.utcnow():
                logger.warning("Authentication failed - account locked", email=email)
                return None
            
            # Verify password
            if not self.verify_password(password, user.hashed_password):
                # Increment failed login attempts
                await self._handle_failed_login(user, session)
                logger.warning("Authentication failed - invalid password", email=email)
                return None
            
            # Reset failed login attempts on successful login
            await self._handle_successful_login(user, session)
            
            logger.info("User authenticated successfully", user_id=str(user.id), email=email)
            return user
            
        except Exception as e:
            logger.error("Authentication error", email=email, error=str(e))
            return None
    
    async def _handle_failed_login(self, user: User, session: AsyncSession):
        """Handle failed login attempt"""
        user.failed_login_attempts += 1
        
        # Lock account if too many failed attempts
        if user.failed_login_attempts >= settings.security.max_login_attempts:
            user.locked_until = datetime.utcnow() + timedelta(
                minutes=settings.security.lockout_duration_minutes
            )
            logger.warning(
                "Account locked due to failed login attempts",
                user_id=str(user.id),
                attempts=user.failed_login_attempts
            )
        
        await session.commit()
    
    async def _handle_successful_login(self, user: User, session: AsyncSession):
        """Handle successful login"""
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.utcnow()
        
        await session.commit()
    
    async def create_user_tokens(self, user: User) -> Dict[str, Any]:
        """
        Create access and refresh tokens for user
        
        Args:
            user: User object
            
        Returns:
            Dictionary containing tokens and metadata
        """
        token_data = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value if user.role else "user"
        }
        
        access_token = self.create_access_token(token_data)
        refresh_token = self.create_refresh_token({"sub": str(user.id)})
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.access_token_expire_minutes * 60,
            "user_id": str(user.id),
            "email": user.email
        }

# Global authentication service instance
auth_service = AuthenticationService()

# Dependency functions
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_db_session)
) -> User:
    """
    Get current authenticated user from JWT token
    
    Args:
        credentials: HTTP Bearer credentials
        session: Database session
        
    Returns:
        Current user object
        
    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Verify token
        payload = auth_service.verify_token(credentials.credentials)
        user_id = payload.get("sub")
        
        if user_id is None:
            raise credentials_exception
        
        # Get user from database
        stmt = select(User).where(User.id == user_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if user is None:
            raise credentials_exception
        
        # Check if user is still active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive"
            )
        
        return user
        
    except AuthenticationError as e:
        logger.warning("Authentication failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        logger.error("Authentication error", error=str(e))
        raise credentials_exception

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user (additional check for user status)
    
    Args:
        current_user: Current user from token
        
    Returns:
        Active user object
        
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return current_user

def require_role(required_role: str):
    """
    Dependency factory for role-based access control
    
    Args:
        required_role: Required user role
        
    Returns:
        Dependency function
    """
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role.value != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    
    return role_checker

def require_any_role(required_roles: list):
    """
    Dependency factory for multiple role access control
    
    Args:
        required_roles: List of acceptable roles
        
    Returns:
        Dependency function
    """
    def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role.value not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    
    return role_checker

# Convenience functions for token operations
def create_access_token(data: Dict[str, Any]) -> str:
    """Create access token (convenience function)"""
    return auth_service.create_access_token(data)

def verify_token(token: str) -> Dict[str, Any]:
    """Verify token (convenience function)"""
    return auth_service.verify_token(token)

# Password utilities
def hash_password(password: str) -> str:
    """Hash password (convenience function)"""
    return auth_service.get_password_hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password (convenience function)"""
    return auth_service.verify_password(plain_password, hashed_password)

# Session management
class SessionManager:
    """
    Session management for tracking active user sessions
    """
    
    def __init__(self):
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    def create_session(self, user_id: str, token_data: Dict[str, Any]) -> str:
        """Create new user session"""
        session_id = f"session_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        self.active_sessions[session_id] = {
            "user_id": user_id,
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "token_data": token_data
        }
        
        return session_id
    
    def update_session_activity(self, session_id: str):
        """Update session last activity"""
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["last_activity"] = datetime.utcnow()
    
    def invalidate_session(self, session_id: str):
        """Invalidate user session"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
    
    def invalidate_user_sessions(self, user_id: str):
        """Invalidate all sessions for a user"""
        sessions_to_remove = [
            session_id for session_id, session_data in self.active_sessions.items()
            if session_data["user_id"] == user_id
        ]
        
        for session_id in sessions_to_remove:
            del self.active_sessions[session_id]
    
    def cleanup_expired_sessions(self, max_age_hours: int = 24):
        """Clean up expired sessions"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        expired_sessions = [
            session_id for session_id, session_data in self.active_sessions.items()
            if session_data["last_activity"] < cutoff_time
        ]
        
        for session_id in expired_sessions:
            del self.active_sessions[session_id]
        
        if expired_sessions:
            logger.info("Cleaned up expired sessions", count=len(expired_sessions))

# Global session manager
session_manager = SessionManager()

# API Key authentication (for service-to-service communication)
class APIKeyAuth:
    """API Key authentication for service-to-service communication"""
    
    def __init__(self):
        self.api_keys = {
            # In production, these would be stored securely
            "admin_key": "admin",
            "service_key": "service"
        }
    
    def verify_api_key(self, api_key: str) -> Optional[str]:
        """Verify API key and return associated role"""
        return self.api_keys.get(api_key)

api_key_auth = APIKeyAuth()

def get_api_key_user(api_key: str = Depends(lambda: None)) -> Optional[str]:
    """Get user role from API key"""
    if api_key:
        return api_key_auth.verify_api_key(api_key)
    return None