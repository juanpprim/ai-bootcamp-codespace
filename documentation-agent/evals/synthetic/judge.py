"""
Three LLM judge checks for evaluating the documentation agent:

1. Answer Correctness  – does the agent's answer contain the reference answer?
2. Instruction Following – does the agent follow its system-prompt instructions?
3. Trajectory Optimality – was the tool-call sequence efficient?
"""

from typing import Literal, Any, Dict

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from doc_agent import DEFAULT_INSTRUCTIONS


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class CorrectnessResult(BaseModel):
    """Result of the answer-correctness check."""

    reasoning: str = Field(
        description="Step-by-step reasoning about whether the agent's answer covers the reference answer."
    )
    score: Literal["good", "bad"] = Field(
        description="'good' if the answer semantically contains the reference answer, 'bad' otherwise."
    )


class InstructionFollowingResult(BaseModel):
    """Result of the instruction-following check."""

    reasoning: str = Field(
        description="Step-by-step reasoning about whether the agent followed its instructions."
    )
    score: Literal["good", "bad"] = Field(
        description="'good' if the agent followed the instructions, 'bad' otherwise."
    )


class TrajectoryResult(BaseModel):
    """Result of the trajectory-optimality check."""

    reasoning: str = Field(
        description="Step-by-step reasoning about the optimality of the tool-call trajectory."
    )
    score: Literal["good", "bad"] = Field(
        description="'good' if the trajectory was reasonably optimal, 'bad' if clearly wasteful."
    )
    suggestion: str = Field(
        description="Concrete suggestion for how the agent could have been more efficient, or 'none' if the trajectory was already optimal."
    )


# ---------------------------------------------------------------------------
# Check 1 – Answer correctness
# ---------------------------------------------------------------------------

CORRECTNESS_INSTRUCTIONS = """
You are an expert evaluator. Your task is to decide whether an AI agent's
answer SEMANTICALLY CONTAINS the reference answer.

Rules:
- The agent's answer does NOT need to be word-for-word identical to the
  reference answer. It must convey the same key information.
- If the reference answer is a code snippet, the agent's answer must include
  equivalent code (variable names may differ, but the logic must match).
- If the agent's answer provides additional correct information beyond the
  reference, that is fine — it should still be marked "good".
- If the agent's answer is missing the core information from the reference
  answer, or contradicts it, mark it "bad".

Be strict: the core facts from the reference answer MUST appear in the
agent's response.
""".strip()

CORRECTNESS_PROMPT = """
User Question:
{question}

Reference Answer (ground truth):
{reference_answer}

Agent's Answer:
{agent_answer}
""".strip()


def create_correctness_judge() -> Agent:
    return Agent(
        name="correctness_judge",
        model="openai:gpt-4o-mini",
        instructions=CORRECTNESS_INSTRUCTIONS,
        output_type=CorrectnessResult,
    )


def format_correctness_prompt(entry: Dict[str, Any]) -> str:
    return CORRECTNESS_PROMPT.format(
        question=entry["input"]["question"],
        reference_answer=entry["input"]["reference_answer"],
        agent_answer=entry["rag_response"]["answer"],
    )


# ---------------------------------------------------------------------------
# Check 2 – Instruction following
# ---------------------------------------------------------------------------

INSTRUCTION_FOLLOWING_INSTRUCTIONS = """
You are an expert evaluator. You will be given:
1. The system-prompt instructions that were given to a documentation agent.
2. A user question the agent received.
3. The agent's response.

Your task is to verify whether the agent FOLLOWED its instructions.

Mark "good" if the agent followed the instructions well overall.
Mark "bad" if the agent violated any important instruction.
""".strip()

INSTRUCTION_FOLLOWING_PROMPT = """
=== AGENT INSTRUCTIONS (system prompt) ===
{instructions}

=== USER QUESTION ===
{question}

=== AGENT ANSWER ===
{agent_answer}

=== AGENT SELF-CHECKS ===
{self_checks}
""".strip()


def create_instruction_judge() -> Agent:
    return Agent(
        name="instruction_judge",
        model="openai:gpt-4o-mini",
        instructions=INSTRUCTION_FOLLOWING_INSTRUCTIONS,
        output_type=InstructionFollowingResult,
    )


def format_instruction_prompt(entry: Dict[str, Any]) -> str:
    checks = entry["rag_response"].get("checks", [])
    checks_str = "\n".join(
        f"- [{'+' if c['passed'] else '-'}] {c['rule']}: {c['explanation']}"
        for c in checks
    )
    return INSTRUCTION_FOLLOWING_PROMPT.format(
        instructions=DEFAULT_INSTRUCTIONS,
        question=entry["input"]["question"],
        agent_answer=entry["rag_response"]["answer"],
        self_checks=checks_str or "(none)",
    )


# ---------------------------------------------------------------------------
# Check 3 – Trajectory optimality
# ---------------------------------------------------------------------------

TRAJECTORY_INSTRUCTIONS = """
You are an expert evaluator. You will be given:
1. A user question.
2. The sequence of tool calls (the "trajectory") the agent made.
3. The agent's final answer.

The agent has two tools:
- search(query) — searches the documentation index and returns matching filenames.
- get_file(filename) — retrieves the full content of a specific documentation file.

The expected workflow (from the agent's instructions) is:
  Iteration 1: one search call.
  Iteration 2: up to 2 more searches + one or more get_file calls.
  Iteration 3: synthesize the answer (no tool calls).

Evaluate the trajectory for optimality:
- Were the search queries relevant and well-formulated?
- Did the agent retrieve the right files?
- Were there redundant or duplicate tool calls? (e.g. calling get_file on the
  same file twice is bad)
- Did the agent make too many or too few tool calls? 3 searches or more is excessive
- Could the agent have reached the same answer with fewer steps?

Mark "good" if the trajectory was reasonably efficient.
Mark "bad" if there are clear inefficiencies (duplicate calls, irrelevant
searches, excessive tool use, or missing obvious files).
Provide a concrete suggestion for improvement, or "none" if optimal.
""".strip()

TRAJECTORY_PROMPT = """
User Question:
{question}

Tool Call Trajectory:
{tools}

Agent's Final Answer:
{agent_answer}
""".strip()


def create_trajectory_judge() -> Agent:
    return Agent(
        name="trajectory_judge",
        model="openai:gpt-4o-mini",
        instructions=TRAJECTORY_INSTRUCTIONS,
        output_type=TrajectoryResult,
    )


def format_trajectory_prompt(entry: Dict[str, Any]) -> str:
    tools_parts = []
    for i, t in enumerate(entry["tools"], 1):
        tools_parts.append(f"{i}. {t['name']}({t['args']})")
    tools_str = "\n".join(tools_parts) or "(no tool calls)"

    return TRAJECTORY_PROMPT.format(
        question=entry["input"]["question"],
        tools=tools_str,
        agent_answer=entry["rag_response"]["answer"],
    )
