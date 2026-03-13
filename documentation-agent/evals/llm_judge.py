import json
from typing import Literal, Any, Dict
from pydantic import BaseModel, Field
from pydantic_ai import Agent

judge_instructions = """
You are an expert evaluator assessing the performance of a documentation assistant (RAG agent). 
You will be provided with the user's question, the tools the agent used, and the agent's final response.
Your task is to review the interaction and classify the agent's response as either "good" or "bad".

A response is "good" if:
1. It accurately and completely answers the user's question, or correctly states it cannot answer if the information is missing.
2. It uses the appropriate tools correctly.
3. The format is easy to read and follows good markdown practices.

A response is "bad" if:
1. It is factually incorrect, misses the point, or hallucinates.
2. It fails to answer the user's question despite having the information in the documentation.
3. It uses the wrong tools or fails to extract the necessary information.
4. It includes raw internal tool outputs instead of user-friendly text or has poor formatting.

Take a step-by-step approach to reason about the quality before providing your final label.
""".strip()

class JudgeEvaluation(BaseModel):
    """
    The output format for the LLM Judge evaluating a RAG log entry.
    """
    reasoning: str = Field(
        description="A step-by-step reasoning evaluating the agent's response against the criteria."
    )
    label: Literal["good", "bad"] = Field(
        description="The final evaluation label for the response: 'good' or 'bad'."
    )

def create_log_judge_agent() -> Agent:
    """
    Creates and returns the judge agent configured to evaluate RAG logs.
    """
    return Agent(
        name="log_judge",
        model="openai:gpt-4o-mini",
        instructions=judge_instructions,
        output_type=JudgeEvaluation
    )

judge_prompt_template = """
Evaluate the agent's performance for the following interaction.

User Question:
{question}

Tools Used:
{tools}

Agent Response:
{answer}
"""

def format_judge_prompt(log_entry: Dict[str, Any]) -> str:
    """
    Formats a single log entry from results.json into a prompt for the judge agent.
    """
    question = log_entry["input"]["question"]
    answer = log_entry["rag_response"]["answer"]
    tools_list = log_entry["tools"]

    tools_str_parts = []
    for t in tools_list:
        name = t['name']
        args = t['args']
        tools_str_parts.append(f"{name}({args})")

    tools = "\n".join(tools_str_parts)
    
    return judge_prompt_template.format(
        question=question,
        tools=tools,
        answer=answer
    )
