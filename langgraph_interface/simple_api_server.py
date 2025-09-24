#!/usr/bin/env python3
"""
Open Interface API Server
A LangGraph-compatible API server that integrates with the Agent Chat UI
Provides real-time streaming of AI actions and thinking processes
"""
import asyncio
import json
import sys
import os
from typing import Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Add the app directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))
sys.path.append(os.path.dirname(__file__))

try:
    from langgraph_interface.graph import OpenInterfaceGraph
except ImportError:
    from graph import OpenInterfaceGraph

app = FastAPI(title="Open Interface API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global graph instance
graph = None

class Message(BaseModel):
    id: str = None
    type: str = "human"
    content: List[dict] = None

class Request(BaseModel):
    input: dict = None
    messages: List[Message] = None

@app.on_event("startup")
async def startup_event():
    """Initialize the LangGraph on startup"""
    global graph
    try:
        graph = OpenInterfaceGraph()
        print("✅ LangGraph Open Interface initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize LangGraph: {e}")
        raise

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "Open Interface API is running", "status": "healthy"}

@app.get("/info")
async def info():
    """API info endpoint"""
    return {
        "name": "Open Interface API",
        "version": "1.0.0",
        "description": "AI assistant that controls computers using PyAutoGUI tools"
    }

@app.post("/assistants/search")
async def search_assistants():
    """Search for assistants"""
    return {
        "assistants": [
            {
                "assistant_id": "open-interface",
                "name": "Open Interface",
                "description": "AI assistant that controls computers using PyAutoGUI tools"
            }
        ]
    }

@app.get("/assistants/{assistant_id}")
async def get_assistant(assistant_id: str):
    """Get assistant details"""
    if assistant_id != "open-interface":
        raise HTTPException(status_code=404, detail="Assistant not found")
    
    return {
        "assistant_id": "open-interface",
        "name": "Open Interface",
        "description": "AI assistant that controls computers using PyAutoGUI tools"
    }

@app.post("/threads")
async def create_thread():
    """Create a new thread"""
    import uuid
    thread_id = str(uuid.uuid4())
    return {"thread_id": thread_id}

@app.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    """Get thread information"""
    return {"thread_id": thread_id}

@app.get("/threads/{thread_id}/runs")
async def list_thread_runs(thread_id: str):
    """List runs for a thread"""
    return []

@app.get("/threads/{thread_id}/messages")
async def get_thread_messages(thread_id: str):
    """Get messages for a thread"""
    return []

@app.post("/threads/{thread_id}/history")
async def get_thread_history(thread_id: str):
    """Get thread history"""
    return []

@app.post("/threads/{thread_id}/runs/stream")
async def stream_thread_run_simple(thread_id: str, request: Request):
    """Stream run execution for a thread - Simple format"""
    return await stream_thread_run("open-interface", thread_id, request)

@app.post("/assistants/{assistant_id}/threads/{thread_id}/runs/stream")
async def stream_thread_run(assistant_id: str, thread_id: str, request: Request):
    """Stream run execution for a thread - LangGraph SDK compatible"""
    if not graph:
        raise HTTPException(status_code=500, detail="Graph not initialized")
    
    # Parse the request body
    try:
        body = request.json()
        # If body is a string, parse it as JSON
        if isinstance(body, str):
            import json
            body = json.loads(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {str(e)}")
    
    # Extract user message from LangGraph SDK format
    user_message = None
    messages = []
    
    # Handle the LangGraph SDK request format
    if "input" in body and "messages" in body["input"]:
        messages = body["input"]["messages"]
    elif "messages" in body:
        messages = body["messages"]
    
    # Extract text from messages
    for message in messages:
        if isinstance(message, dict):
            if message.get("type") == "human":
                content = message.get("content", [])
                if isinstance(content, list):
                    for content_item in content:
                        if content_item.get("type") == "text":
                            user_message = content_item.get("text")
                            break
                elif isinstance(content, str):
                    user_message = content
                break
    
    if not user_message:
        raise HTTPException(status_code=400, detail="No user message found")
    
    try:
        from fastapi.responses import StreamingResponse
        import uuid
        
        async def generate_stream():
            try:
                # Send initial thinking message
                thinking_content = f"🤔 I'll help you {user_message}. Let me think about this step by step..."
                yield f"event: updates\ndata: {json.dumps({'agent': {'messages': [{'id': str(uuid.uuid4()), 'type': 'ai', 'content': thinking_content}]}})}\n\n"
                
                # Stream execution
                for chunk in graph.stream_execution(user_message):
                    if "planning" in chunk:
                        planning_data = chunk["planning"]
                        steps = planning_data.get("current_instructions", {}).get("steps", [])
                        status_updates = planning_data.get("status_updates", [])
                        
                        # Stream status updates from planning
                        for status in status_updates:
                            yield f"event: updates\ndata: {json.dumps({'planning': {'messages': [{'id': str(uuid.uuid4()), 'type': 'ai', 'content': f'📋 {status}'}]}})}\n\n"
                        
                        if steps:
                            # Show planned steps as tool calls
                            tool_calls = []
                            for step in steps:
                                if step.get("function"):
                                    tool_calls.append({
                                        "id": str(uuid.uuid4()),
                                        "name": step["function"].replace("pyautogui.", ""),
                                        "args": step.get("parameters", {}),
                                        "type": "tool_call"
                                    })
                            
                            if tool_calls:
                                yield f"event: updates\ndata: {json.dumps({'planning': {'messages': [{'id': str(uuid.uuid4()), 'type': 'ai', 'content': 'Here are the actions I\'ll perform:', 'tool_calls': tool_calls}]}})}\n\n"
                    
                    elif "execution" in chunk:
                        execution_data = chunk["execution"]
                        
                        # Stream status updates as real-time thinking messages
                        status_updates = execution_data.get("status_updates", [])
                        for status in status_updates:
                            yield f"event: updates\ndata: {json.dumps({'execution': {'messages': [{'id': str(uuid.uuid4()), 'type': 'ai', 'content': f'⚡ {status}'}]}})}\n\n"
                        
                        # Stream execution results
                        results = execution_data.get("execution_results", [])
                        for result in results:
                            # Stream the justification as thinking
                            justification = result.get('justification', '')
                            if justification:
                                yield f"event: updates\ndata: {json.dumps({'execution': {'messages': [{'id': str(uuid.uuid4()), 'type': 'ai', 'content': f'🔧 {justification}'}]}})}\n\n"
                            
                            # Stream the tool result
                            tool_message = {
                                "id": str(uuid.uuid4()),
                                "type": "tool",
                                "content": f"✅ {result.get('result', 'Success')}",
                                "name": result.get("function", "").replace("pyautogui.", "")
                            }
                            yield f"event: updates\ndata: {json.dumps({'execution': {'messages': [tool_message]}})}\n\n"
                    
                    elif "validation" in chunk:
                        if chunk["validation"].get("is_complete"):
                            yield f"event: updates\ndata: {json.dumps({'validation': {'messages': [{'id': str(uuid.uuid4()), 'type': 'ai', 'content': '🎯 Task validation complete...'}]}})}\n\n"
                    
                    elif "response" in chunk:
                        response_text = "✨ Task completed successfully!"
                        
                        if "messages" in chunk["response"]:
                            for msg in chunk["response"]["messages"]:
                                if hasattr(msg, 'content') and msg.content:
                                    response_text = f"✨ {msg.content}"
                                    break
                        
                        yield f"event: updates\ndata: {json.dumps({'response': {'messages': [{'id': str(uuid.uuid4()), 'type': 'ai', 'content': response_text}]}})}\n\n"
                
                # Send done event
                yield f"event: done\ndata: {json.dumps({})}\n\n"
                
            except Exception as e:
                error_data = {
                    "type": "error",
                    "error": str(e)
                }
                yield f"data: {json.dumps(error_data)}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming failed: {str(e)}")

@app.get("/assistants")
async def list_assistants():
    """List all assistants"""
    return [{
        "assistant_id": "open-interface",
        "name": "Open Interface",
        "description": "AI assistant that controls computers using PyAutoGUI tools"
    }]

@app.get("/assistants/{assistant_id}/runs/{run_id}")
async def get_run(assistant_id: str, run_id: str):
    """Get run status"""
    return {
        "run_id": run_id,
        "assistant_id": assistant_id,
        "status": "completed"
    }

if __name__ == "__main__":
    print("🚀 Starting Open Interface API Server...")
    print("📡 Server will be available at: http://localhost:2024")
    print("🔗 Connect the Agent Chat UI to: http://localhost:2024")
    print("🤖 Assistant ID: open-interface")
    print("✨ Real-time streaming of AI actions enabled")
    
    uvicorn.run(
        "simple_api_server:app",
        host="0.0.0.0",
        port=2024,
        reload=True,
        log_level="info"
    )
