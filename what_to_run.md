# arxiv

bash run.sh  
python collect_parse_paper_questions.py
python refine_questions.py

output: outputs/parse-paper-fast-refined

# wiki

refine_wiki_questions.py

output: outputs/wikipedia-refined

# google

bash run_google.sh
python collect_google_questions.py
python refine_google_questions.py

output: outputs/google-refined
