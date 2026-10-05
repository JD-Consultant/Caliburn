from common import *
check_manifest();check_manifest('rerank-input-manifest.json');check_manifest('benchmark-code-manifest.json')
from gpu_worker import main
main()
