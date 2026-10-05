"""Input variants need their own identity, in addition to the sealed task guard."""
from support import prior
from audit import check_benchmark_task

def check_task(row,expected,q,response=None):
    assert row['variant']==expected['variant'],'benchmark input variant mislabeled'
    check_benchmark_task(row,expected,q,response)
