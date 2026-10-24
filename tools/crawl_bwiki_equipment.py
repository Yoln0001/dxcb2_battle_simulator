"""One-shot equipment extraction; use --from-html for an already downloaded page."""
from pathlib import Path
import sys,argparse,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.unclassified_equipment.crawler import parse_equipment
from backend.unclassified_equipment.store import UnclassifiedEquipmentStore
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--from-html',type=Path);args=parser.parse_args()
    store=UnclassifiedEquipmentStore(Path(__file__).resolve().parents[1]/'data/unclassified_equipment.json')
    result=store.merge(*parse_equipment(args.from_html.read_text(encoding='utf-8'))) if args.from_html else store.refresh()
    print(json.dumps({'fetched':result['fetched'],'added':result['added'],'counts':result['counts']},ensure_ascii=True))
