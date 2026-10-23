"""Checks on coordinating-agents that ship with neither skill: neutrality and correspondence."""

import re
import unittest

from tools.check_skills import ROOT

SKILL = ROOT / "skills" / "coordinating-agents"
CRITERIA = ROOT / "skills" / "auditing-repositories" / "references" / "criteria-agents.md"

# Providers, models, products, and options of one agent tool. The skill names mechanisms instead;
# each repository's profile names its own (docs/decisions.md, "Provider-neutral coordination").
NAMED = [
    "anthropic", "openai", "google", "gemini", "deepmind", "deepseek", "z.ai", "zhipu", "mistral",
    "llama", "qwen", "grok", "xai", "kimi", "moonshot", "nvidia", "azure", "bedrock", "vertex ai",
    "gemma", "mixtral", "cohere", "ollama", "groq",
    "claude", "opus", "sonnet", "haiku", "fable", "gpt", "chatgpt", "codex", "glm", "sol", "astra",
    "copilot", "cursor", "aider", "windsurf", "cline", "devin", "cachettl", "autocompactwindow",
    "maxturns", "allowedtools", "disallowedtools", "setting-sources", "safe-mode", "setup-token",
    "pretooluse", "subagent_type",
]
# Letters around a term make another word; digits, punctuation, and underscores do not, so
# `GPT5`, `glm4.6`, and `claude_code` are names while `console` and `resolve` are not.
NAMED_PATTERN = re.compile(
    r"(?<![a-z])(" + "|".join(re.escape(term) for term in NAMED) + r")(?![a-z])", re.IGNORECASE
)

# Each audit criterion on agents, mapped to the sections of this skill that carry it out
# (docs/decisions.md, "Separate guides for auditing and coordinating").
CORRESPONDENCE = {
    "AGENT-02": [("references/briefs.md", "The brief")],
    "AGENT-03": [("references/review.md", "Independent review"), ("references/review.md", "Verify claims")],
    "AGENT-04": [("references/shared-state.md", "Isolation"), ("references/shared-state.md", "Close-out at merge")],
    "AGENT-05": [("references/shared-state.md", "Shared resources"), ("references/shared-state.md", "The state record")],
}


def named_terms(text: str) -> list[str]:
    return [match.group(1) for match in NAMED_PATTERN.finditer(text)]


def headings(path, level: str = "##") -> list[str]:
    return [line[len(level) + 1:].strip() for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith(level + " ")]


class NeutralityTests(unittest.TestCase):
    def test_the_skill_names_no_provider_model_or_tool_option(self):
        files = sorted(SKILL.rglob("*.md"))
        self.assertTrue(files)
        found = {str(path.relative_to(SKILL)): named_terms(path.read_text(encoding="utf-8"))
                 for path in files}
        self.assertEqual({path: terms for path, terms in found.items() if terms}, {})

    def test_the_matcher_finds_names_and_skips_ordinary_words(self):
        self.assertEqual(named_terms("Route reviews to Sonnet, set cacheTtl, ask GPT-6 or z.ai."),
                         ["Sonnet", "cacheTtl", "GPT", "z.ai"])
        self.assertEqual(named_terms("GPT5, Sonnet5, glm4.6, claude_code, x-opus, Vertex AI"),
                         ["GPT", "Sonnet", "glm", "claude", "opus", "Vertex AI"])
        self.assertEqual(named_terms("solve the console, metadata, a resolution, consolidate; gptx"), [])


class LengthTests(unittest.TestCase):
    def test_the_procedure_stays_within_its_word_cap(self):
        # The audit skill's long procedure displaced judgment; this one is capped at 1,000 words.
        body = (SKILL / "SKILL.md").read_text(encoding="utf-8").split("\n---\n", 1)[1]
        self.assertLessEqual(len(body.split()), 1000)


class CorrespondenceTests(unittest.TestCase):
    def test_each_agent_criterion_has_its_sections_in_the_skill(self):
        criteria = CRITERIA.read_text(encoding="utf-8")
        for identifier, sections in CORRESPONDENCE.items():
            with self.subTest(identifier=identifier):
                self.assertIn(f"| {identifier} |", criteria)
                for relative, heading in sections:
                    self.assertIn(heading, headings(SKILL / relative), relative)

    def test_the_profile_template_lists_every_cost_strategy(self):
        cost = (SKILL / "references" / "cost.md").read_text(encoding="utf-8")
        section = cost.split("\n## Strategies\n", 1)[1].split("\n## ", 1)[0]
        strategies = re.findall(r"^### (.+)$", section, re.MULTILINE)
        profile = (SKILL / "references" / "profile.md").read_text(encoding="utf-8")
        table = profile.split("| Strategy | Adopted | Reason |\n| --- | --- | --- |\n", 1)[1]
        rows = re.findall(r"^\| ([^|]+?) \|", table.split("\n\n", 1)[0], re.MULTILINE)
        self.assertGreater(len(strategies), 1)
        self.assertEqual(rows, strategies)


if __name__ == "__main__":
    unittest.main()
