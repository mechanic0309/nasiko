import os
import json
import re
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage


class AgentGenerator:
    def __init__(
        self,
        model_name="gpt-4o-mini",
        output_dir="generated_agents",
        cards_per_iter=5,
        sample_agent_cards=None,
    ):
        self.model_name = model_name
        self.output_dir = output_dir
        self.llm = ChatOpenAI(model=model_name, temperature=0.9)
        self.cards_per_iter = cards_per_iter
        self.sample_agent_cards = json.dumps(sample_agent_cards, indent=2)
        self.names, self.descriptions = self._get_names_and_descriptions()

        # Create the output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)

    def generate_prompt(self):
        system_prompt = (
            f"Create {self.cards_per_iter} new agent cards for agents with a realistic and useful purpose and all the agents should be distinct. "
            "Be creative while coming up with the agents. Create agents that are useful for a diverse set of tasks. "
            "Change all fields like id (random UUID-like string), name, description, id of each skill, "
            "name of each skill, and all text-related fields to match the new agent purpose. "
            "Note that the defaultInputModes and defaultOutputModes fields can be overridden by the inputModes and outputModes of skills. "
            "Do not omit or rename any field, even if null. "
            "Each agent card should be a valid JSON object. Your output should be a valid JSON array of agent cards. "
            "Do not include markdown, commentary, or extra formatting."
        )

        user_prompt = ""
        if self.sample_agent_cards is not None:
            user_prompt = (
                f"Here are 3-4 sample agent cards:\n{self.sample_agent_cards}\n"
            )

        # TODO: Pass names along with descriptions.
        if len(self.descriptions) > 0:
            print(f"There are {len(self.descriptions)} names and descriptions")

            names_and_descriptions = "\n".join(
                f"Name: {n}, Description: {d}"
                for n, d in zip(self.names, self.descriptions)
            )
            user_prompt += (
                f"\n\nNames and Descriptions of previously generated agents:\n"
                f"{names_and_descriptions}\n\nPlease ensure none of the new agents have similar or overlapping names or descriptions. "
                "The new agents you generate must do tasks different from those done by these agents."
            )

        return [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]

    def generate_agent_cards(self, num_iters=20):
        # Find the highest numbered response_{n}.json file
        max_response_index = -1
        for filename in os.listdir(self.output_dir):
            match = re.match(r"response_(\d+)\.json", filename)
            if match:
                index = int(match.group(1))
                max_response_index = max(max_response_index, index)

        # Find the highest numbered agent_{m}.json file
        max_agent_index = -1
        for filename in os.listdir(self.output_dir):
            match = re.match(r"agent_card_(\d+)\.json", filename)
            if match:
                index = int(match.group(1))
                max_agent_index = max(max_agent_index, index)

        # Start from next available indices
        response_index = max_response_index + 1
        agent_index = max_agent_index + 1

        print(f"Starting responses from index: {response_index}")
        print(f"Starting agent files from index: {agent_index}")

        for i in range(num_iters):
            prompt = self.generate_prompt()
            response = self.llm.invoke(prompt)
            response_text = response.content.strip()

            try:
                agents_json = json.loads(response_text)
            except Exception as e:
                print(response_text)
                print(f"Warning: Response not valid JSON on iteration {i}: {e}")
                continue

            filename = os.path.join(self.output_dir, f"response_{response_index}.json")
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(agents_json, f, indent=2, ensure_ascii=False)
            response_index += 1

            if isinstance(agents_json, dict):
                agents = agents_json.get("agents", [])
                if not isinstance(agents, list):
                    print(f"No valid 'agents' list in response on iteration {i}")
                    continue
            elif isinstance(agents_json, list):
                agents = agents_json
            else:
                print(f"No valid 'agents' list in response on iteration {i}")
                continue

            print(f"\n=== Iteration {i}: Saving {len(agents)} agents ===")

            # Save each agent to its own JSON file
            # Use the calculated index for agent files
            for agent in agents:
                desc = agent.get("description", "")
                if desc:
                    self.descriptions.append(desc)
                else:
                    print(
                        f"Warning: No description found for an agent on iteration {i}"
                    )

                filename = os.path.join(
                    self.output_dir, f"agent_card_{agent_index}.json"
                )
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(agent, f, indent=2, ensure_ascii=False)

                agent_index += 1
                print(f"Saved {filename}")
            print(f"Length of descriptions: {len(self.descriptions)}")

        print("\nAll iterations complete.")

    def _get_names_and_descriptions(self):
        """
        Reads all JSON files in the generated_agents folder and extracts their names and descriptions.

        Returns:
            list: A list of names string and description strings from all agent JSON files.
        """
        names = []
        descriptions = []
        agents_path = Path(self.output_dir)

        # Check if the folder exists
        if not agents_path.exists():
            print(f"Warning: Folder '{self.output_dir}' does not exist.")
            return names, descriptions

        # Find all JSON files recursively in the folder
        json_files = list(agents_path.rglob("agent_card_*.json"))

        if not json_files:
            print(f"Warning: No JSON files found in '{self.output_dir}'.")
            return names, descriptions

        print(f"Found {len(json_files)} JSON files in '{self.output_dir}'")

        # Read each JSON file and extract the description
        for json_file in json_files:
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Extract description if it exists
                name = data.get("name", "")
                description = data.get("description", "")
                if name and description:
                    names.append(name)
                    descriptions.append(description)
                    print(f"Extracted name and description from {json_file.name}")
                else:
                    print(f"No name or no description found in {json_file.name}")

            except json.JSONDecodeError as e:
                print(f"Error parsing JSON in {json_file.name}: {e}")
            except Exception as e:
                print(f"Error reading {json_file.name}: {e}")

        assert len(names) == len(descriptions)
        print(
            f"\nExtracted {len(names)} names and descriptions from {len(json_files)} files."
        )
        return names, descriptions


# Example usage:
if __name__ == "__main__":
    sample_agent_cards = [
        {
            "protocolVersion": "0.2.9",
            "name": "Compliance Checker Agent",
            "description": "An agent that analyzes documents for policy violations and compliance issues.",
            "url": "http://localhost:10008/",
            "preferredTransport": "JSONRPC",
            "provider": {
                "organization": "Nasiko AI Projects",
                "url": "https://github.com/ashishsharma/nasiko",
            },
            "iconUrl": "http://localhost:10008/icon.png",
            "version": "1.0.0",
            "documentationUrl": "http://localhost:10008/docs",
            "capabilities": {
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": True,
                "chat_agent": False,
            },
            "securitySchemes": {},
            "security": [],
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "skills": [
                {
                    "id": "compliance_checking",
                    "name": "Compliance Checking",
                    "description": "Analyze documents for policy violations and compliance issues.",
                    "tags": [
                        "compliance",
                        "policy",
                        "document-analysis",
                        "regulations",
                    ],
                    "examples": [
                        "Check this document for policy compliance",
                        "Does this email violate any policies?",
                        "Analyze this expense report for compliance issues",
                        "What are the encryption requirements for file transfers?",
                    ],
                    "inputModes": ["text"],
                    "outputModes": ["text"],
                },
                {
                    "id": "check-compliance",
                    "name": "Check Compliance",
                    "description": "Check document for policy compliance.",
                    "tags": ["compliance", "document", "policy"],
                    "examples": [
                        "Check this document for compliance issues.",
                        "Is this report compliant with company policies?",
                    ],
                    "inputModes": ["text"],
                    "outputModes": ["application/json"],
                },
                {
                    "id": "analyze-policy",
                    "name": "Analyze Policy",
                    "description": "Answer questions about policies.",
                    "tags": ["policy", "questions", "analysis"],
                    "examples": [
                        "What are the data retention policies?",
                        "Explain the policy on remote work.",
                    ],
                    "inputModes": ["text"],
                    "outputModes": ["application/json"],
                },
            ],
            "supportsAuthenticatedExtendedCard": False,
            "signatures": [],
        },
        {
            "protocolVersion": "0.2.9",
            "name": "a2a-github-agent",
            "description": "An intelligent GitHub agent built with A2A (Agent2Agent) SDK that can query GitHub repositories, recent updates, commits, and project activity using natural language.",
            "url": "http://localhost:10007/",
            "preferredTransport": "JSONRPC",
            "provider": {
                "organization": "Nasiko AI Projects",
                "url": "https://github.com/ashishsharma/nasiko",
            },
            "iconUrl": "http://localhost:10007/icon.png",
            "version": "1.0.0",
            "documentationUrl": "http://localhost:10007/docs",
            "capabilities": {
                "streaming": True,
                "pushNotifications": False,
                "stateTransitionHistory": True,
                "chat_agent": False,
            },
            "securitySchemes": {},
            "security": [],
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["text/plain"],
            "skills": [
                {
                    "id": "get-user-repositories",
                    "name": "Get User Repositories",
                    "description": "Get user's repositories with recent updates.",
                    "tags": ["github", "repositories", "updates"],
                    "examples": [
                        "Show my recent repository updates",
                        "List repositories updated in the last 7 days",
                    ],
                    "inputModes": ["application/json"],
                    "outputModes": ["application/json"],
                },
                {
                    "id": "get-recent-commits",
                    "name": "Get Recent Commits",
                    "description": "Get recent commits for a repository.",
                    "tags": ["github", "commits", "repository"],
                    "examples": [
                        "What are the latest commits in my project?",
                        "Show commits from the last 3 days",
                    ],
                    "inputModes": ["application/json"],
                    "outputModes": ["application/json"],
                },
                {
                    "id": "search-repositories",
                    "name": "Search Repositories",
                    "description": "Search for repositories with recent activity.",
                    "tags": ["github", "search", "repositories"],
                    "examples": [
                        "Search for popular Python repositories with recent activity",
                        "Find repositories with the most stars",
                    ],
                    "inputModes": ["application/json"],
                    "outputModes": ["application/json"],
                },
            ],
            "supportsAuthenticatedExtendedCard": False,
            "signatures": [],
        },
        {
            "protocolVersion": "0.2.9",
            "name": "CrewAI",
            "description": "This sample demonstrates a simple image generation agent built with CrewAI and exposed through the A2A protocol.",
            "url": "http://localhost:10001/",
            "preferredTransport": "JSONRPC",
            "provider": {
                "organization": "Nasiko AI Projects",
                "url": "https://github.com/ashishsharma/nasiko",
            },
            "iconUrl": "http://localhost:10001/icon.png",
            "version": "1.0.0",
            "documentationUrl": "http://localhost:10001/docs",
            "capabilities": {
                "streaming": False,
                "pushNotifications": False,
                "stateTransitionHistory": True,
                "chat_agent": False,
            },
            "securitySchemes": {},
            "security": [],
            "defaultInputModes": ["application/json", "text/plain"],
            "defaultOutputModes": ["application/json", "image/png"],
            "skills": [
                {
                    "id": "image_generator",
                    "name": "Image Generator",
                    "description": "Generate stunning, high-quality images on demand and leverage powerful editing capabilities to modify, enhance, or completely transform visuals.",
                    "tags": ["generate image", "edit image"],
                    "examples": [
                        "Generate a photorealistic image of raspberry lemonade"
                    ],
                    "inputModes": ["application/json", "text/plain"],
                    "outputModes": ["application/json", "image/png"],
                }
            ],
            "supportsAuthenticatedExtendedCard": False,
            "signatures": [],
        },
        {
            "protocolVersion": "0.2.9",
            "name": "langgraph",
            "description": "This sample demonstrates a currency conversion agent built with [LangGraph](https://langchain-ai.github.io/langgraph/) and exposed through the A2A protocol. It showcases conversational interactions with support for multi-turn dialogue and streaming responses.",
            "url": "http://localhost:10000/",
            "preferredTransport": "JSONRPC",
            "provider": {
                "organization": "Nasiko AI Projects",
                "url": "https://github.com/ashishsharma/nasiko",
            },
            "iconUrl": "http://localhost:10000/icon.png",
            "version": "1.0.0",
            "documentationUrl": "http://localhost:10000/docs",
            "capabilities": {
                "streaming": True,
                "pushNotifications": True,
                "stateTransitionHistory": True,
                "chat_agent": False,
            },
            "securitySchemes": {},
            "security": [],
            "defaultInputModes": ["application/json", "text/plain"],
            "defaultOutputModes": ["application/json"],
            "skills": [
                {
                    "id": "get-exchange-rate",
                    "name": "Get Exchange Rate",
                    "description": "Use this to get current exchange rate.",
                    "tags": ["currency conversion", "exchange rate"],
                    "examples": ["What is the exchange rate between USD and EUR?"],
                    "inputModes": ["application/json", "text/plain"],
                    "outputModes": ["application/json"],
                }
            ],
            "supportsAuthenticatedExtendedCard": False,
            "signatures": [],
        },
    ]

    output_dir = "data/agent_cards"
    agent_generator = AgentGenerator(
        output_dir=output_dir, cards_per_iter=10, sample_agent_cards=sample_agent_cards
    )
    agent_generator.generate_agent_cards(num_iters=10)
