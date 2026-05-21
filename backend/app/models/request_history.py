"""Request History models for Firestore durable storage."""

from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field


class RequestHistory(BaseModel):
    """
    Canonical schema for durable request history in Firestore.
    
    This model captures all fields required for audit, investigation, and analytics.
    Documents should be written to the 'requests' collection with TTL policy enabled.
    
    Attributes:
        id: Deterministic request ID (format: req_{timestamp}_{hash})
        timestamp: ISO 8601 UTC timestamp of the request
        user_id: User identifier from auth context
        team: Optional team identifier
        model: Actual model used (post-fallback)
        original_model: Originally requested model
        input_tokens: Prompt token count
        output_tokens: Completion token count
        total_tokens: Sum of input and output tokens
        blocked: Whether the request was blocked by budget/rate policy
        downgraded: Whether the model was downgraded
        block_reason: Reason code if blocked (e.g., "budget_exceeded", "rate_limit")
        latency_ms: Total request latency in milliseconds
        expires_at: TTL field for 90-day auto-deletion (Firestore TTL policy)
    """
    
    id: str = Field(..., description="Deterministic request ID")
    timestamp: datetime = Field(..., description="ISO 8601 UTC timestamp")
    user_id: str = Field(..., description="User identifier from auth context")
    team: Optional[str] = Field(None, description="Team identifier")
    model: str = Field(..., description="Actual model used (post-fallback)")
    original_model: str = Field(..., description="Originally requested model")
    input_tokens: int = Field(0, description="Prompt token count")
    output_tokens: int = Field(0, description="Completion token count")
    total_tokens: int = Field(0, description="Sum of input and output tokens")
    blocked: bool = Field(False, description="Whether request was blocked")
    downgraded: bool = Field(False, description="Whether model was downgraded")
    block_reason: Optional[str] = Field(None, description="Reason code if blocked")
    latency_ms: int = Field(0, description="Total request latency in milliseconds")
    expires_at: datetime = Field(..., description="TTL field for 90-day auto-deletion")
    
    @classmethod
    def from_request_context(
        cls,
        request_id: str,
        timestamp: datetime,
        user_id: str,
        team: Optional[str],
        model: str,
        original_model: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        blocked: bool,
        downgraded: bool,
        block_reason: Optional[str],
        latency_ms: int,
        ttl_days: int = 90
    ) -> "RequestHistory":
        """
        Factory function to build RequestHistory from FastAPI request context.
        
        Args:
            request_id: Deterministic request ID
            timestamp: Request timestamp
            user_id: User identifier
            team: Optional team identifier
            model: Actual model used
            original_model: Originally requested model
            input_tokens: Prompt tokens
            output_tokens: Completion tokens
            total_tokens: Total tokens
            blocked: Whether blocked
            block_reason: Block reason if applicable
            latency_ms: Request latency
            ttl_days: TTL in days (default 90)
            
        Returns:
            RequestHistory instance with expires_at calculated
        """
        expires_at = datetime.utcnow() + timedelta(days=ttl_days)
        
        return cls(
            id=request_id,
            timestamp=timestamp,
            user_id=user_id,
            team=team,
            model=model,
            original_model=original_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            blocked=blocked,
            downgraded=downgraded,
            block_reason=block_reason,
            latency_ms=latency_ms,
            expires_at=expires_at,
        )
    
    def to_firestore(self) -> dict:
        """
        Convert to Firestore-compatible dictionary.
        
        Returns:
            Dictionary suitable for Firestore document set/create
        """
        return self.model_dump()
    
    @classmethod
    def from_firestore(cls, data: dict) -> "RequestHistory":
        """
        Build from Firestore document data.
        
        Args:
            data: Dictionary from Firestore document
            
        Returns:
            RequestHistory instance
        """
        return cls(**data)
