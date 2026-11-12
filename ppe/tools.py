"""Read-only section tools bound to the startup catalogue."""

from langchain_core.tools import tool
from pydantic import BaseModel, ConfigDict, Field

from ppe.evidence import SECTIONS, Catalogue
from ppe.prompts import TOOL_DESCRIPTIONS


class FundSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fund_ids: list[str] = Field(min_length=1, max_length=25)


def build_tools(catalogue: Catalogue) -> dict:
    def section_tool(section, description):
        @tool("get_" + section, args_schema=FundSelection, description=description)
        def retrieve(fund_ids: list[str]) -> dict:
            return catalogue.retrieve(section, fund_ids)

        return retrieve

    tools = [section_tool(section, TOOL_DESCRIPTIONS[section]) for section in SECTIONS]
    tools.append(
        tool("list_options", description=TOOL_DESCRIPTIONS["list_options"])(
            catalogue.options
        )
    )
    return {item.name: item for item in tools}
