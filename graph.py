from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from agent1 import agent1
from agent2 import agent2
from agent3 import agent3
from agent4 import agent4, is_risk_summary_question, is_recommendation_question, is_insight_question

class State(TypedDict, total=False):
    loan_acct_number: str
    question: str
    route: str
    agent1_output: str
    risk_score: float
    risk_category: str
    recommended_actions: str
    answer: str
    citations: list
    queries_used: list
    tools_used: list
    chat_history: list
    execution_trace: list

def add_trace(state, name):
    trace = list(state.get("execution_trace", []))
    if name not in trace:
        trace.append(name)
    return trace

def router(state):
    route = state.get("route", "agent4")
    if route == "agent1":
        return "agent1"
    if route == "agent2":
        return "agent2"
    if route == "agent3":
        if state.get("recommended_actions"):
            return "end"
        if not state.get("agent1_output"):
            return "agent1"
        if state.get("risk_score") is None or not state.get("risk_category"):
            return "agent2"
        return "agent3"
    question = state.get("question", "")
    insight_question = is_insight_question(question)
    risk_question = is_risk_summary_question(question)
    recommendation_question = is_recommendation_question(question)
    if recommendation_question:
        if not state.get("agent1_output"):
            return "agent1"
        if state.get("risk_score") is None or not state.get("risk_category"):
            return "agent2"
        if not state.get("recommended_actions"):
            return "agent3"
        return "agent4"
    if insight_question and not state.get("agent1_output"):
        return "agent1"
    if risk_question and (state.get("risk_score") is None or not state.get("risk_category")):
        return "agent2"
    return "agent4"

def run_agent1(state):
    if state.get("agent1_output"):
        return {}
    result = agent1(state)
    result["execution_trace"] = add_trace(state, "Agent 1 - Smart Insights")
    return result

def run_agent2(state):
    if state.get("risk_score") is not None and state.get("risk_category"):
        return {}
    result = agent2(state)
    result["execution_trace"] = add_trace(state, "Agent 2 - Risk Summary")
    return result

def run_agent3(state):
    if state.get("recommended_actions"):
        return {}
    result = agent3(state)
    result["execution_trace"] = add_trace(state, "Agent 3 - Recommended Actions")
    return result

def run_agent4(state):
    result = agent4(state)
    result["execution_trace"] = add_trace(state, "Agent 4 - Chat")
    return result

def after_agent1(state):
    route = state.get("route", "agent4")
    if route == "agent1":
        return "end"
    if route == "agent3":
        if state.get("risk_score") is None or not state.get("risk_category"):
            return "agent2"
        return "agent3"
    question = state.get("question", "")
    if is_recommendation_question(question):
        if state.get("risk_score") is None or not state.get("risk_category"):
            return "agent2"
        if not state.get("recommended_actions"):
            return "agent3"
    return "agent4"

def after_agent2(state):
    route = state.get("route", "agent4")
    if route == "agent2":
        return "end"
    if route == "agent3":
        return "agent3"
    question = state.get("question", "")
    if is_recommendation_question(question):
        return "agent3"
    return "agent4"

def after_agent3(state):
    route = state.get("route", "agent4")
    if route == "agent3":
        return "end"
    return "agent4"

graph_builder = StateGraph(State)
graph_builder.add_node("router", lambda state: state)
graph_builder.add_node("agent1", run_agent1)
graph_builder.add_node("agent2", run_agent2)
graph_builder.add_node("agent3", run_agent3)
graph_builder.add_node("agent4", run_agent4)
graph_builder.add_edge(START, "router")

graph_builder.add_conditional_edges("router", router, {
    "agent1": "agent1",
    "agent2": "agent2",
    "agent3": "agent3",
    "agent4": "agent4",
    "end": END
})

graph_builder.add_conditional_edges("agent1", after_agent1, {
    "agent2": "agent2",
    "agent3": "agent3",
    "agent4": "agent4",
    "end": END
})

graph_builder.add_conditional_edges("agent2", after_agent2, {
    "agent3": "agent3",
    "agent4": "agent4",
    "end": END
})

graph_builder.add_conditional_edges("agent3", after_agent3, {
    "agent4": "agent4",
    "end": END
})

graph_builder.add_edge("agent4", END)
graph = graph_builder.compile()

if __name__ == "__main__":
    try:
        png_bytes = graph.get_graph().draw_mermaid_png()
        with open("graph.png", "wb") as f:
            f.write(png_bytes)
        print("graph.png generated successfully")
    except Exception as e:
        print(f"Could not generate graph.png: {e}")
