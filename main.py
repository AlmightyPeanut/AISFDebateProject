# add naive (no access to the document and (non-interactive) debate)
# add different strategies for debate?
# - never admit defeat (Trump tactic)
# - make stuff up about the original text
from load_data import Dataset

# investigate without the quote system
# tried to mitigate self-defeating behaviour, but were unsuccessful

if __name__ == '__main__':
    data = Dataset()
    for article, question, correct_answer, false_answer in data:
        pass
