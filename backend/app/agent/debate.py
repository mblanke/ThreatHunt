import asyncio

async def debated_generate(provider, prompt: str) -> str:
    """
    Minimal behind-the-scenes debate.
    Same logic for all apps.
    Advisory only. No execution.
    """

    planner = f"""
You are the Planner.
Give structured advisory guidance only.
No execution. No tools.

Request:
{prompt}
"""

    critic = f"""
You are the Critic.
Identify risks, missing steps, and assumptions.
No execution. No tools.

Request:
{prompt}
"""

    pragmatist = f"""
You are the Pragmatist.
Suggest the safest and simplest approach.
No execution. No tools.

Request:
{prompt}
"""

    planner_task = provider.generate(planner)
    critic_task = provider.generate(critic)
    prag_task = provider.generate(pragmatist)

    planner_resp, critic_resp, prag_resp = await asyncio.gather(
        planner_task, critic_task, prag_task
    )

    judge = f"""
You are the Judge.

Merge the three responses into ONE final advisory answer.

Rules:
- Advisory only
- No execution
- Clearly list risks and assumptions
- Be concise

Planner:
{planner_resp}

Critic:
{critic_resp}

Pragmatist:
{prag_resp}
"""

    final = await provider.generate(judge)
    return final
