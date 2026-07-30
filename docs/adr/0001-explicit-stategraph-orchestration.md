# Use an explicit StateGraph for controlled agent orchestration

GigaBacklog Agent uses an explicit LangGraph `StateGraph` instead of a prebuilt `create_react_agent`. The graph makes the mandatory single tool call, bounded validation retry, human review, and audit transitions deterministic and visible while GigaChat still chooses the search query and produces the recommendation.
