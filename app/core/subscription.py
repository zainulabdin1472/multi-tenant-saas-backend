"""Subscription plan limits config."""

from dataclasses import dataclass


@dataclass
class SubscriptionPlan:
    """Subscription plan with limits."""

    project_limit: int | None
    task_limit_per_project: int | None


SUBSCRIPTION_PLANS: dict[str, SubscriptionPlan] = {
    "free": SubscriptionPlan(project_limit=3, task_limit_per_project=10),
    "pro": SubscriptionPlan(project_limit=None, task_limit_per_project=None),
    "enterprise": SubscriptionPlan(project_limit=None, task_limit_per_project=None),
}


def get_plan(plan_name: str) -> SubscriptionPlan:
    """Get subscription plan by name. Defaults to free."""
    return SUBSCRIPTION_PLANS.get(plan_name.lower(), SUBSCRIPTION_PLANS["free"])
