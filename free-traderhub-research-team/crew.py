"""crew.py — FreeTraderHub Agentic Marketing Research Team."""

import os
from datetime import date

from crewai import Agent, Task, Crew, Process, LLM
from crewai_tools import ScrapeWebsiteTool

from config import (
    MODEL,
    BASE_URL,
    DISCLAIMER,
    FORBIDDEN_PHRASES,
    MIN_RESEARCH_WORDS,
    MIN_REDDIT_POSTS,
    MIN_BLOG_WORDS,
    SITE_NAME,
    SITE_URL,
    SITE_DESCRIPTION,
    CALCULATORS,
    COMPETITORS,
)
from tools import get_reddit_hot_posts, scan_all_subreddits, get_finance_headlines, read_gsc_csv, duckduckgo_search

TODAY = date.today().isoformat()
REPORTS_DIR = os.path.join("reports", TODAY)


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def _make_llm(temperature: float = 0.3) -> LLM:
    """Return a CrewAI LLM instance pointing at the configured local Ollama model."""
    return LLM(
        model=MODEL,
        base_url=BASE_URL,
        temperature=temperature,
    )


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

def _team_lead() -> Agent:
    return Agent(
        role="Marketing Research Team Lead",
        goal=(
            "Coordinate the research team, delegate tasks to the right specialist, "
            "quality-gate every output against the configured minimums "
            f"(research ≥{MIN_RESEARCH_WORDS} words, reddit ≥{MIN_REDDIT_POSTS} posts, "
            f"blog ≥{MIN_BLOG_WORDS} words), replan and re-delegate if any output falls "
            "short, and write a clear executive brief summarising insights and next actions."
        ),
        backstory=(
            f"You are the head of the {SITE_NAME} marketing research function. "
            "You have a sharp eye for quality and never let substandard work through. "
            "You delegate efficiently, check every deliverable against the team's quality "
            "standards, and synthesise findings into actionable strategy."
        ),
        llm=_make_llm(temperature=0.1),
        allow_delegation=True,
        verbose=True,
        memory=False,
        max_iter=8,
    )


def _researcher() -> Agent:
    return Agent(
        role="Senior Market Researcher",
        goal=(
            f"Conduct deep market research for {SITE_NAME} ({SITE_URL}). "
            "Identify trends, competitor moves, and keyword opportunities relevant to "
            f"forex/crypto calculators. Competitors to watch: {', '.join(COMPETITORS)}."
        ),
        backstory=(
            f"You are a senior researcher with 10+ years analysing the retail forex and "
            "crypto trading tool landscape. You use web search and content scraping to "
            "produce structured, evidence-backed research reports."
        ),
        llm=_make_llm(),
        tools=[duckduckgo_search, ScrapeWebsiteTool(), get_finance_headlines],
        allow_delegation=False,
        verbose=True,
        memory=False,
        max_iter=5,
    )


def _monitor() -> Agent:
    return Agent(
        role="Community Intelligence Monitor",
        goal=(
            "Monitor Reddit trading communities for pain points, questions, and discussions "
            f"related to {', '.join(CALCULATORS)} calculators. Identify threads where "
            f"{SITE_NAME} could add genuine value."
        ),
        backstory=(
            "You are a community intelligence specialist embedded in retail trading forums. "
            "You read between the lines of Reddit posts to surface real user problems and "
            "content gaps that a helpful calculator site can address."
        ),
        llm=_make_llm(),
        tools=[get_reddit_hot_posts, scan_all_subreddits],
        allow_delegation=False,
        verbose=True,
        memory=False,
        max_iter=4,
    )


def _analyst() -> Agent:
    return Agent(
        role="Growth Strategy Analyst",
        goal=(
            f"Analyse {SITE_NAME}'s Google Search Console data to identify underperforming "
            "queries, high-impression / low-CTR opportunities, and content gaps. "
            "Translate data into a prioritised weekly growth action plan."
        ),
        backstory=(
            "You are a growth analyst who lives in Search Console data. "
            "You spot patterns that others miss and convert raw query data into "
            "concrete, prioritised recommendations."
        ),
        llm=_make_llm(),
        tools=[read_gsc_csv],
        allow_delegation=False,
        verbose=True,
        memory=False,
        max_iter=4,
    )


def _writer() -> Agent:
    forbidden_str = "\n".join(f'  - "{p}"' for p in FORBIDDEN_PHRASES)
    return Agent(
        role="Compliant Content Writer",
        goal=(
            f"Write SEO-optimised, compliant content for {SITE_NAME} that is genuinely "
            "helpful to retail traders. Every piece must pass the compliance checklist "
            "before submission."
        ),
        backstory=(
            f"You are a specialist financial content writer. You MUST adhere to the "
            f"following rules without exception:\n\n"
            f"DISCLAIMER (include verbatim at the end of every piece):\n{DISCLAIMER}\n\n"
            f"FORBIDDEN PHRASES — never use any of these:\n{forbidden_str}\n\n"
            "EDITOR'S NOTE TAGS: Wherever personal trading experience or a first-person "
            "anecdote would strengthen the copy, insert a tag like:\n"
            "  [EDITOR'S NOTE: Add a brief personal experience about <topic> here.]\n"
            "Do NOT fabricate personal stories. Flag them for the human editor instead.\n\n"
            f"Minimum blog post length: {MIN_BLOG_WORDS} words.\n"
            "Always write in second person ('you') and educational tone."
        ),
        llm=_make_llm(),
        tools=[],
        allow_delegation=False,
        verbose=True,
        memory=False,
        max_iter=5,
    )


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def _tasks(
    team_lead: Agent,
    researcher: Agent,
    monitor: Agent,
    analyst: Agent,
    writer: Agent,
) -> list[Task]:

    research_task = Task(
        description=(
            f"Conduct a comprehensive market research report for {SITE_NAME} ({SITE_URL}).\n"
            f"Site offers: {SITE_DESCRIPTION}\n"
            f"Competitors: {', '.join(COMPETITORS)}\n\n"
            "Cover:\n"
            "1. Current trends in forex/crypto retail trading tools (cite sources).\n"
            "2. Competitor feature analysis — what are they doing that we are not?\n"
            "3. Finance news headlines relevant to our audience this week.\n"
            "4. Top 5 keyword/content opportunities identified from search.\n\n"
            f"Minimum output: {MIN_RESEARCH_WORDS} words. Use headings. Save to the output file."
        ),
        expected_output=(
            f"A structured market research report of at least {MIN_RESEARCH_WORDS} words "
            "with sections: Trends, Competitor Analysis, News Headlines, Keyword Opportunities."
        ),
        agent=researcher,
        output_file=os.path.join(REPORTS_DIR, "01_market_research.md"),
    )

    monitor_task = Task(
        description=(
            "Scan all configured subreddits and produce a community intelligence report.\n\n"
            "Cover:\n"
            "1. Top trending threads by score and engagement.\n"
            f"2. Posts where users ask about {', '.join(CALCULATORS)}.\n"
            "3. Pain points and unanswered questions we could address with content.\n"
            "4. Three specific Reddit threads worth responding to (include post URL and why).\n\n"
            f"Minimum: {MIN_REDDIT_POSTS} posts analysed. Save to the output file."
        ),
        expected_output=(
            f"A community intelligence report analysing at least {MIN_REDDIT_POSTS} Reddit posts, "
            "with trending threads, pain points, and 3 reply opportunities."
        ),
        agent=monitor,
        context=[research_task],
        output_file=os.path.join(REPORTS_DIR, "02_community_monitor.md"),
    )

    analyst_task = Task(
        description=(
            "Analyse the Google Search Console export and community data to produce a "
            "prioritised weekly growth strategy.\n\n"
            "Cover:\n"
            "1. GSC summary: top queries by clicks, hidden gems (high impressions, low CTR).\n"
            "2. Content gaps identified by combining GSC + Reddit insights.\n"
            "3. Top 3 priority actions for this week (ranked by impact).\n"
            "4. One calculator to promote this week and why.\n\n"
            "If GSC file is missing, note it and base the strategy on Reddit + research data."
        ),
        expected_output=(
            "A weekly growth strategy with GSC analysis, content gaps, top 3 actions, "
            "and a featured calculator recommendation."
        ),
        agent=analyst,
        context=[research_task, monitor_task],
        output_file=os.path.join(REPORTS_DIR, "03_weekly_strategy.md"),
    )

    writer_task = Task(
        description=(
            f"Using the weekly strategy, write the following content for {SITE_NAME}:\n\n"
            "1. BLOG POST (≥700 words): Educational article targeting the top keyword "
            "opportunity. Include H2/H3 headings, internal links to our calculators, "
            "and the full disclaimer at the end.\n\n"
            "2. THREE SOCIAL POSTS:\n"
            "   - Twitter/X: ≤280 chars, punchy, no hype\n"
            "   - LinkedIn: professional tone, 2–3 sentences\n"
            "   - Reddit-style: conversational, helpful, no sales language\n\n"
            "3. ONE EMAIL SUBJECT LINE + PREVIEW TEXT for the weekly newsletter.\n\n"
            "Flag any section needing personal experience with [EDITOR'S NOTE: ...] tags. "
            "Never use forbidden phrases. Include the disclaimer verbatim at the end of the blog post."
        ),
        expected_output=(
            f"A blog post ≥{MIN_BLOG_WORDS} words, three platform-specific social posts, "
            "and one email subject+preview. All compliant with disclaimer and no forbidden phrases."
        ),
        agent=writer,
        context=[analyst_task],
        output_file=os.path.join(REPORTS_DIR, "04_content_drafts.md"),
    )

    brief_task = Task(
        description=(
            "Review all four deliverables and write the executive brief.\n\n"
            "Quality gate — reject and re-request if:\n"
            f"  • Market research < {MIN_RESEARCH_WORDS} words\n"
            f"  • Reddit report covers < {MIN_REDDIT_POSTS} posts\n"
            f"  • Blog post < {MIN_BLOG_WORDS} words\n"
            "  • Any forbidden phrase appears in the content drafts\n\n"
            "The brief must contain:\n"
            "1. SITUATION (2–3 sentences): what the market is doing right now.\n"
            "2. INSIGHTS (bullet list): top 5 findings across all reports.\n"
            "3. THIS WEEK'S ACTIONS (numbered list): exactly what to do, in priority order.\n"
            "4. CONTENT PIPELINE: blog title, social post status, email subject.\n"
            "5. METRICS TO WATCH: 3 KPIs to check at next week's run.\n"
        ),
        expected_output=(
            "A concise executive brief covering Situation, Insights, This Week's Actions, "
            "Content Pipeline, and Metrics to Watch."
        ),
        agent=team_lead,
        context=[research_task, monitor_task, analyst_task, writer_task],
        output_file=os.path.join(REPORTS_DIR, "00_executive_brief.md"),
    )

    return [research_task, monitor_task, analyst_task, writer_task, brief_task]


# ---------------------------------------------------------------------------
# Build crew
# ---------------------------------------------------------------------------

def build_crew() -> Crew:
    """Instantiate all agents and tasks and return a configured hierarchical Crew."""
    team_lead = _team_lead()
    researcher = _researcher()
    monitor = _monitor()
    analyst = _analyst()
    writer = _writer()

    tasks = _tasks(team_lead, researcher, monitor, analyst, writer)

    return Crew(
        agents=[researcher, monitor, analyst, writer],
        tasks=tasks,
        manager_agent=team_lead,
        process=Process.hierarchical,
        verbose=True,
        memory=False,
    )
