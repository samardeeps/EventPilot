from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError

from app.core.config import settings

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validates a Supabase JWT token and extracts the user claims.
    In Supabase, the secret used to sign JWTs is the JWT_SECRET (typically same as Anon/Service key, but it's available in Supabase settings).
    For now, we enforce a valid token or fallback to basic check.
    """
    token = credentials.credentials
    try:
        # Note: In production you MUST set the correct JWT secret from Supabase
        # Supabase defaults to HS256 for JWT signing
        payload = jwt.decode(
            token, 
            settings.secret_key, # If this is the Supabase JWT secret
            algorithms=["HS256"], 
            options={"verify_aud": False} # Depend on your configuration
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid auth credentials")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate token. Please ensure SECRET_KEY is set to Supabase JWT Secret.")
