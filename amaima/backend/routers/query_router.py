# backend/routers/query_router.py

from fastapi import APIRouter, Depends, UploadFile, File, Form
from typing import List, Optional
from pydantic import BaseModel

router = APIRouter(prefix="/v1/query", tags=["queries"])

class QueryRequest(BaseModel):
    query: str
    operation: str = "general"
    file_ids: Optional[List[str]] = None
    context: Optional[dict] = None

class QueryResponse(BaseModel):
    query_id: str
    response_text: str
    model_used: str
    confidence: float
    latency_ms: int
    supports_streaming: bool = True
    file_references: Optional[List[dict]] = None

@router.post("", response_model=QueryResponse)
async def submit_query(
    request: QueryRequest,
    current_user = Depends(get_current_user)
):
    """Submit a query for processing with optional file attachments"""
    
    # Build query context
    context = request.context or {}
    
    # Process file attachments
    file_contents = []
    if request.file_ids:
        for file_id in request.file_ids:
            file_metadata = await get_file_metadata(file_id, current_user.id)
            
            if not file_metadata:
                raise ApiException(
                    code="FILE_NOT_FOUND",
                    message=f"File {file_id} not found",
                    status_code=404
                )
            
            # Download and parse file content
            file_content = await download_and_parse_file(file_metadata)
            file_contents.append({
                "filename": file_metadata.filename,
                "content": file_content,
                "type": file_metadata.mime_type
            })
            
            # Add file reference to response
            context.setdefault("file_references", []).append({
                "file_id": file_id,
                "filename": file_metadata.filename
            })
    
    # Enhance query with file contents
    enhanced_query = request.query
    if file_contents:
        file_context = "\n\n".join([
            f"--- File: {f['filename']} ---\n{f['content']}"
            for f in file_contents
        ])
        enhanced_query = f"{request.query}\n\nRelevant file contents:\n{file_context}"
    
    # Route query through smart router
    routing_decision = await smart_router.route(
        enhanced_query,
        request.operation,
        user_context={
            "user_id": current_user.id,
            "tier": current_user.subscription_tier
        }
    )
    
    # Process query with selected model
    start_time = time.time()
    response_text = await process_query_with_model(
        enhanced_query,
        routing_decision.model_name,
        context=context
    )
    latency_ms = int((time.time() - start_time) * 1000)
    
    # Verify response quality
    verification = await verify_response(
        response_text,
        enhanced_query,
        routing_decision.model_name
    )
    
    # Log query for analytics
    await log_query(
        user_id=current_user.id,
        query=request.query,
        response=response_text,
        model=routing_decision.model_name,
        latency_ms=latency_ms,
        confidence=verification.confidence,
        file_count=len(file_contents)
    )
    
    return QueryResponse(
        query_id=str(uuid.uuid4()),
        response_text=response_text,
        model_used=routing_decision.model_name,
        confidence=verification.confidence,
        latency_ms=latency_ms,
        supports_streaming=True,
        file_references=context.get("file_references")
    )
