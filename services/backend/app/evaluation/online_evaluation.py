import asyncio
from evaluation.evaluators import EvaluatorProtocol, direct_metrics
from evaluation.evaluators import llm_judge_evaluator_factual_accuracy_grounded
from evaluation.evaluators import llm_judge_evaluator_relevance
from evaluation.evaluators import llm_judge_evaluator_clarity
from evaluation.evaluators import llm_judge_evaluator_completeness
from evaluation.evaluators import llm_judge_evaluator_safety
from evaluation.evaluators import llm_judge_evaluator_faithfulness
from packages.langfuse.client import get_langfuse_client
from schemas.evaluation import EvalRunResult

evaluators: list[EvaluatorProtocol] = [
    direct_metrics,
    llm_judge_evaluator_factual_accuracy_grounded,
    llm_judge_evaluator_relevance,
    llm_judge_evaluator_clarity,
    llm_judge_evaluator_completeness,
    llm_judge_evaluator_safety,
    llm_judge_evaluator_faithfulness,
]


async def evaluate_online(eval_result: EvalRunResult) -> None:
    """Evaluate the online result.

    Args:
        eval_result: The evaluation result to evaluate.
    """

    tasks = [evaluator(eval_result) for evaluator in evaluators]
    evs_results = await asyncio.gather(*tasks)

    evs = [ev for ev_results in evs_results for ev in ev_results or []]

    langfuse_client = get_langfuse_client()
    if not langfuse_client:
        return

    for ev in evs:

        langfuse_client.create_score(
            trace_id=eval_result.trace_id,
            name=ev.name,
            value=ev.value,
            comment=ev.comment,
            data_type="NUMERIC",
        )
