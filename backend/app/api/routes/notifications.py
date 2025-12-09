from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
import json

from app.core.database import get_db
from app.core.deps import get_current_active_user
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationRead, NotificationUpdate

router = APIRouter()

# Store active WebSocket connections
active_connections: dict[int, List[WebSocket]] = {}


@router.get("/", response_model=List[NotificationRead])
async def list_notifications(
    skip: int = 0,
    limit: int = 50,
    unread_only: bool = False,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List notifications for current user
    
    Supports filtering by read/unread status.
    """
    query = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.tenant_id == current_user.tenant_id
    )
    
    if unread_only:
        query = query.filter(Notification.is_read == False)
    
    notifications = query.order_by(Notification.created_at.desc()).offset(skip).limit(limit).all()
    return notifications


@router.put("/{notification_id}", response_model=NotificationRead)
async def update_notification(
    notification_id: int,
    notification_update: NotificationUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update notification (mark as read/unread)
    """
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    notification.is_read = notification_update.is_read
    db.commit()
    db.refresh(notification)
    
    return notification


@router.post("/mark-all-read")
async def mark_all_read(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Mark all notifications as read for current user
    """
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    
    return {"message": "All notifications marked as read"}


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time notifications
    
    Clients should send their token on connect, then receive notifications in real-time.
    """
    await websocket.accept()
    user_id = None
    
    try:
        # Wait for authentication message
        auth_data = await websocket.receive_text()
        auth_json = json.loads(auth_data)
        token = auth_json.get("token")
        
        # Validate token and get user (simplified - in production use proper auth)
        from app.core.security import verify_token
        payload = verify_token(token)
        if payload:
            user_id = payload.get("sub")
            
            # Register connection
            if user_id not in active_connections:
                active_connections[user_id] = []
            active_connections[user_id].append(websocket)
            
            # Send confirmation
            await websocket.send_json({"type": "connected", "user_id": user_id})
            
            # Keep connection alive
            while True:
                data = await websocket.receive_text()
                # Echo back for keepalive
                await websocket.send_json({"type": "pong"})
        else:
            await websocket.close(code=1008)  # Policy violation
            
    except WebSocketDisconnect:
        # Remove connection
        if user_id and user_id in active_connections:
            active_connections[user_id].remove(websocket)
            if not active_connections[user_id]:
                del active_connections[user_id]
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close(code=1011)  # Internal error


async def send_notification_to_user(user_id: int, notification: dict):
    """
    Send notification to all connected clients for a user
    
    Args:
        user_id: User ID to send notification to
        notification: Notification data to send
    """
    if user_id in active_connections:
        disconnected = []
        for websocket in active_connections[user_id]:
            try:
                await websocket.send_json({
                    "type": "notification",
                    "data": notification
                })
            except:
                disconnected.append(websocket)
        
        # Clean up disconnected websockets
        for ws in disconnected:
            active_connections[user_id].remove(ws)
        
        if not active_connections[user_id]:
            del active_connections[user_id]
