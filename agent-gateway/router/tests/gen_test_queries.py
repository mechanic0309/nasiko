import os
import json
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
from typing import List


class QueryList(BaseModel):
    """List of generated queries."""

    queries: List[str] = Field(
        description="List of generated natural, human-like queries that would trigger this agent."
    )


class QueryGenerator:
    def __init__(
        self,
        model_name="gpt-4o-mini",
        agent_cards_dir="data/agent_cards",
        output_dir="generated_queries",
    ):
        """
        Initialize the QueryGenerator.

        Args:
            model_name: The OpenAI model to use for generation
            agent_cards_dir: Directory containing agent card JSON files
            output_dir: Directory to save generated queries
        """
        self.model_name = model_name
        self.agent_cards_dir = agent_cards_dir
        self.output_dir = output_dir
        # Initialize LLM with structured output
        self.llm = ChatOpenAI(model=model_name, temperature=0.9).with_structured_output(
            QueryList
        )

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

    def load_agent_cards(self):
        """Load all agent cards from the agent_cards_dir."""
        agent_cards_path = Path(self.agent_cards_dir)

        if not agent_cards_path.exists():
            raise FileNotFoundError(
                f"Agent cards directory '{self.agent_cards_dir}' does not exist."
            )

        # Find all JSON files in the agent cards directory
        json_files = sorted(agent_cards_path.glob("agent_card_*.json"))

        if not json_files:
            raise FileNotFoundError(
                f"No agent card files found in '{self.agent_cards_dir}'."
            )

        agent_cards = []
        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    agent_card = json.load(f)
                    agent_cards.append(
                        {"file_name": json_file.name, "data": agent_card}
                    )
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON in {json_file.name}: {e}")
            except Exception as e:
                print(f"Error reading {json_file.name}: {e}")

        print(f"Loaded {len(agent_cards)} agent cards from '{self.agent_cards_dir}'")
        return agent_cards

    def generate_queries_for_agent(self, agent_card, k=5):
        """
        Generate k test queries for a given agent card.

        Args:
            agent_card: The agent card data
            k: Number of queries to generate

        Returns:
            List of generated queries
        """
        agent_name = agent_card.get("name", "Unknown Agent")
        agent_description = agent_card.get("description", "")
        skills = agent_card.get("skills", [])

        # Build a comprehensive context about the agent
        skills = []
        for skill in skills:
            skill_id = skill.get("id", "")
            skill_desc = skill.get("description", "")
            egs = skill.get("examples", [])
            if skill_id and skill_desc:
                skills.append(
                    f"- Skill {skill_id}: {skill_desc}. Sample queries that can be resolved using this skill: {egs}."
                )

        skills_text = "\n".join(skills) if skills else "No specific skills listed"

        system_prompt = f"""You are helping generate realistic test queries for an agent routing system.
Generate {k} natural human queries for the following agent.

The queries should:
1. Sound like what a real human might ask (informal, possibly vague)
2. Include occasional spelling mistakes and grammatical errors
3. Vary in length and specificity
4. Cover different skills of the agent
5. Use different phrasings and wordings

DO NOT make the queries too perfect or formal. Make them realistic and human-like.
You will return a structured list of queries."""

        user_prompt = f"""Agent Name: {agent_name}

Agent Description: {agent_description}

Skills:
{skills_text}

Note that the example queries that go along with skills are just for REFERENCE ONLY, you MUST generate DIFFERENT queries.

Generate {k} new queries for the agent. The queries should sound like natural human requests with imperfections like typos, casual language, etc."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        try:
            response = self.llm.invoke(messages)

            # Response is now a QueryList Pydantic model
            if not response or not response.queries:
                print(f"Warning: No queries generated for agent '{agent_name}'")
                return []

            # Convert Pydantic models to dict format matching the expected output
            queries = [q for q in response.queries]

            return queries

        except Exception as e:
            print(f"Error generating queries for agent '{agent_name}': {e}")
            return []

    def generate_all_queries(self, k=5):
        """
        Generate k queries for each agent card.

        Args:
            k: Number of queries to generate per agent
        """
        agent_cards = self.load_agent_cards()

        all_results = []

        for idx, agent_card_info in enumerate(agent_cards):
            file_name = agent_card_info["file_name"]
            agent_data = agent_card_info["data"]
            agent_name = agent_data.get("name", "Unknown")

            print(
                f"\n[{idx + 1}/{len(agent_cards)}] Generating {k} queries for '{agent_name}' ({file_name})..."
            )

            queries = self.generate_queries_for_agent(agent_data, k=k)

            if queries:
                result = {"agent_name": agent_name, "queries": queries}
                all_results.append(result)

                # Extract the index number from agent_card_i.json to create queries_i.json
                import re

                match = re.search(r"agent_card_(\d+)\.json", file_name)
                if match:
                    card_index = match.group(1)
                    queries_file_name = f"queries_{card_index}.json"
                else:
                    # Fallback if the filename doesn't match expected pattern
                    queries_file_name = f"queries_{idx}.json"

                # Save queries to individual file
                output_file = os.path.join(self.output_dir, queries_file_name)
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)

                print(
                    f"Generated {len(queries)} queries - saved to {queries_file_name}"
                )
            else:
                print(f"Failed to generate queries")

        print(f"\n{'='*60}")
        print(f"Generated queries for {len(all_results)}/{len(agent_cards)} agents")
        print(f"Query files saved to: {self.output_dir}")
        print(f"{'='*60}")

        return all_results


# Example usage
if __name__ == "__main__":
    # Initialize the generator
    generator = QueryGenerator(
        model_name="gpt-4o-mini",
        agent_cards_dir="data/agent_cards",
        output_dir="data/queries",
    )

    # Generate 5 queries for each agent card
    results = generator.generate_all_queries(k=5)
