import json
import os
import re

import polars as pl
import seaborn as sns
from matplotlib import pyplot as plt

from Debate import JUDGE_RESULTS_DIR


def parse_result(judge_response: str, correct_answer_first: bool) -> int:
    judge_answer = re.search(r"answer: (\w)", judge_response.lower())
    if not judge_answer:
        raise RuntimeError("Could not find answer in judge response: " + judge_response)
    judge_answer = judge_answer.group(1).strip()
    if correct_answer_first:
        if judge_answer == "a":
            return 1
        else:
            return 0
    else:
        if judge_answer == "a":
            return 0
        else:
            return 1


def get_file_results(files: list[str]) -> list[dict[str, int]]:
    judge_results = []

    for file_name in files:
        with open(file_name) as f:
            question_id = int(re.search(r"_(\d+).json", file_name).group(1))
            file_contents = json.load(f)
            judge_results.append({
                "question_id": question_id,
                "is_correct_first": 1,
                "is_judge_correct": parse_result(file_contents["correct_first"], True)
            })
            judge_results.append({
                "question_id": question_id,
                "is_correct_first": 0,
                "is_judge_correct": parse_result(file_contents["correct_second"], False)
            })

    return judge_results


if __name__ == '__main__':
    unverified_files = []
    verified_files = []

    for file in os.listdir(JUDGE_RESULTS_DIR):
        if file.startswith('unverified'):
            unverified_files.append(os.path.join(JUDGE_RESULTS_DIR, file))
        elif file.startswith('verified'):
            verified_files.append(os.path.join(JUDGE_RESULTS_DIR, file))

    correct_verified_judgements = get_file_results(verified_files)
    correct_unverified_judgements = get_file_results(unverified_files)

    verified_judgement_results = pl.from_dicts(correct_verified_judgements).with_columns(verified=1)
    unverified_judgement_results = pl.from_dicts(correct_unverified_judgements).with_columns(verified=0)
    print(f"Correct judge classification with quote verification system: {verified_judgement_results["is_judge_correct"].sum()}")
    print(f"Correct judge classification without quote verification system: {unverified_judgement_results["is_judge_correct"].sum()}")

    judgement_results = unverified_judgement_results.vstack(verified_judgement_results)

    # sns.barplot(judgement_results, y="is_judge_correct", hue="verified", errorbar=None, legend=False, gap=.2)
    # plt.xlim((-.4, .4))
    # plt.ylim((.0, 1.))
    # plt.ylabel("Correct Judgement")
    # plt.xticks(ticks=[-0.2, .2], labels=["No", "Yes"])
    # plt.xlabel("Uses verified quote system?")
    # plt.savefig("data/quote_system_results.png")

    joined_judgement_results = verified_judgement_results.drop("verified").join(unverified_judgement_results.drop("verified"),
                                                                         on=["question_id", "is_correct_first"],
                                                                         suffix="_unverified")
    # Where did the quoting system improve the results where did it mislead the judge?
    different_results = joined_judgement_results.filter(
        pl.col("is_judge_correct") != pl.col("is_judge_correct_unverified")
    )
    questions_with_different_results = different_results.select(
        pl.col("question_id"),
        pl.col("is_correct_first"),
    ).sort(by="question_id")
    print(f"{len(questions_with_different_results)} questions with different judgement results when using verified vs unverified quotes.")

    judgement_mislead_by_quote_verification = different_results.filter(
        pl.col("is_judge_correct") == 0
    ).select(
        pl.col("question_id"),
        pl.col("is_correct_first"),
    ).sort(by="question_id")
    print(f"In {len(judgement_mislead_by_quote_verification)} questions the quote verification made judgement worse.")

    judgement_mislead_by_quote_verification = different_results.filter(
        pl.col("is_judge_correct") == 1
    ).select(
        pl.col("question_id"),
        pl.col("is_correct_first"),
    ).sort(by="question_id")
    print(f"In {len(judgement_mislead_by_quote_verification)} questions the quote verification improved judgement.")

    correctly_judged_correct_answer_first = joined_judgement_results.filter(
        pl.col("is_correct_first") == 1
    ).sum().select(pl.col("is_judge_correct"), pl.col("is_judge_correct_unverified"))
    correctly_judged_correct_answer_second = joined_judgement_results.filter(
        pl.col("is_correct_first") == 0
    ).sum().select(pl.col("is_judge_correct"), pl.col("is_judge_correct_unverified"))
    print(f"{correctly_judged_correct_answer_first} questions are correctly judged with the correct answer displayed first.")
    print(f"{correctly_judged_correct_answer_second} questions are correctly judged with the correct answer displayed second.")

    concatted_judgement_results = pl.concat([
        joined_judgement_results.with_columns(
            pl.col("question_id"),
            pl.col("is_correct_first"),
            pl.col("is_judge_correct"),
            verified=1,
        ),
        joined_judgement_results.with_columns(
            pl.col("question_id"),
            pl.col("is_correct_first"),
            pl.col("is_judge_correct_unverified"),
            verified=0,
        ),
    ])

    plt.clf()
    sns.barplot(concatted_judgement_results, x="verified", y="is_judge_correct", hue="is_correct_first", errorbar=None, legend=False)
    plt.legend(title="Correct answer first?", labels=["No", "Yes"])
    plt.ylim((.0, 1.))
    plt.ylabel("Correct Judgement")
    plt.xticks(ticks=[0, 1], labels=["No", "Yes"])
    plt.xlabel("Uses verified quote system?")
    plt.savefig("data/position_bias_results.png")
    # plt.show()

