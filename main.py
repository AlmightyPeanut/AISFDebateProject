from Debate import Debate
from load_data import Dataset

# investigate without the quote system
# tried to mitigate self-defeating behaviour, but were unsuccessful

if __name__ == '__main__':
    data = Dataset()
    for article, question, correct_answer, false_answer, question_id in data:
        print(f"Starting experiment for question {question_id + 1}")
        debate = Debate(question_id=question_id, story=article, question=question, correct_answer=correct_answer,
                        false_answer=false_answer)
        debate.start_discussion(use_quote_verification=True)
        debate.start_discussion(use_quote_verification=False)
        debate.start_judging()
        print()

        if question_id >= 50:
            break

    print("Finished experiments.")
