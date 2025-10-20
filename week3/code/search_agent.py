from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.messages import FunctionToolCallEvent

import search_tools


class NamedCallback:

    def __init__(self, agent):
        self.agent_name = agent.name

    async def print_function_calls(self, ctx, event):
        # Detect nested streams
        if hasattr(event, "__aiter__"):
            async for sub in event:
                await self.print_function_calls(ctx, sub)
            return

        if isinstance(event, FunctionToolCallEvent):
            tool_name = event.part.tool_name
            args = event.part.args
            print(f"TOOL CALL ({self.agent_name}): {tool_name}({args})")

    async def __call__(self, ctx, event):
        return await self.print_function_calls(ctx, event)


search_instructions = """
You are a helpful assistant that answers questions by searching
the documentation.

Requirements:

- For every user query, you must perform at least 3 separate searches
    to gather enough context and verify accuracy.  
- Each search should use a different angle, phrasing, or keyword
    variation of the user's query. 
- After performing all searches, write a concise, accurate answer
    that synthesizes the findings.  
- For each section, include references listing all the sources
    you used to write that section.
""".strip()


class Reference(BaseModel):
    title: str
    filename: str

class Section(BaseModel):
    heading: str
    content: str
    references: list[Reference]


class SearchResultArticle(BaseModel):
    title: str
    sections: list[Section]
    references: list[Reference]

    def format_article(self, base_url: str = "https://github.com/evidentlyai/docs/blob/main"):
        output = f"# {self.title}\n\n"

        for section in self.sections:
            output += f"## {section.heading}\n\n"
            output += f"{section.content}\n\n"
            output += "### References\n"
            for ref in section.references:
                output += f"- [{ref.title}]({base_url}/{ref.filename})\n"

        output += "## References\n"
        for ref in self.references:
            output += f"- [{ref.title}]({base_url}/{ref.filename})\n"

        return output

def create_agent():
    tools = search_tools.prepare_search_tools()

    return Agent(
        name="search",
        instructions=search_instructions,
        tools=[tools.search],
        model="openai:gpt-4o-mini",
        output_type=SearchResultArticle
    )