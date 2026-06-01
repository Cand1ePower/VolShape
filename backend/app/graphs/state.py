from typing import TypedDict, List, Dict, Any, Optional


class AgentState(TypedDict):
    # Core identifiers
    user_input: str
    user_id: str
    session_id: str
    mode: str  # "quick" or "detailed"

    # Intent routing
    intent: str  # "training_plan" | "diet_log" | "chat" | "profile_update"

    # Profile and event context
    user_profile: Dict[str, Any]
    recent_events: List[Dict[str, Any]]
    conversation_history: List[Dict[str, str]]

    # Planning and execution
    plan_steps: List[str]
    execution_results: Dict[str, Any]

    # Tavily search results
    tavily_results: List[Dict[str, Any]]

    # Evaluation / self-reflection
    reflection_result: Dict[str, Any]  # {"score": int, "feedback": str, "risk": str}
    error_count: int
    corrector_feedback: str

    # Output
    final_response: str
    ui_components: Optional[Dict[str, Any]]
    route: str
