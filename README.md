RUN LOCALLY STEPS:

python -m venv venv

source venv/bin/activate   -- for mac

venv\Scripts\activate  -- for winodws

pip install -r requirements.txt

python init_db.py

If theres studybuddy.db from an older version, run migrate instead of re-init
python migrate_db.py

python app.py