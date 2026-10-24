"""Extract BWIKI equipment tables without executing page scripts."""
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.parse import urljoin
from datetime import datetime, timezone
import hashlib,re
from ..skills.store import SkillError
SOURCE_URL='https://wiki.biligame.com/dxcb2/%E8%A3%85%E5%A4%87'
CATEGORIES={'剑':('sword','战士'),'斧':('axe','野蛮人'),'匕首':('dagger','潜行者'),'杖':('staff','法师'),'枪':('gun','火枪手'),'锤':('hammer','圣职'),'防具':('armor',''),'饰品':('accessory','')}
class Node:
    def __init__(self,tag='',attrs=None):self.tag=tag;self.attrs=attrs or {};self.children=[]
    def descendants(self,tag):
        for c in self.children:
            if isinstance(c,Node):
                if c.tag==tag:yield c
                yield from c.descendants(tag)
    def text(self):
        return ''.join(c.text() if isinstance(c,Node) else c for c in self.children)
class Document(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=True);self.root=Node();self.stack=[self.root]
    def handle_starttag(self,tag,attrs):
        node=Node(tag,dict(attrs));self.stack[-1].children.append(node)
        if tag in ('br','hr'):node.children.append('\n')
        if tag not in ('area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'):self.stack.append(node)
    def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs);self.handle_endtag(tag)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:del self.stack[i:];break
    def handle_data(self,value):self.stack[-1].children.append(value)
def clean(value):return '\n'.join(re.sub(r'[ \t\r\xa0]+',' ',line).strip() for line in value.splitlines() if line.strip())
def parse_equipment(html):
    doc=Document();doc.feed(html);records={};counts={key:0 for key,_ in CATEGORIES.values()}
    for row in doc.root.descendants('tr'):
        if 'divsort' not in row.attrs.get('class','').split():continue
        label=row.attrs.get('data-param8','')
        if label not in CATEGORIES:continue
        cells=[c for c in row.children if isinstance(c,Node) and c.tag in ('td','th')]
        if len(cells)!=4:raise SkillError('装备表格列数发生变化，未更新原资料')
        anchors=[a for a in cells[0].descendants('a') if clean(a.text())]
        if not anchors:raise SkillError('装备名称无法解析，未更新原资料')
        link=anchors[0];name=clean(link.text());url=urljoin(SOURCE_URL,link.attrs.get('href',''))
        category,job=CATEGORIES[label];item_id='bwiki_'+hashlib.sha256((category+'|'+url).encode()).hexdigest()[:20]
        if item_id in records:raise SkillError('发现重复装备条目，未更新原资料')
        records[item_id]={'id':item_id,'name':name,'category':category,'categoryLabel':label,'weaponJob':job,'attributes':clean(cells[2].text()),'effects':clean(cells[3].text()),'sourceUrl':url}
        counts[category]+=1
    if any(n==0 for n in counts.values()):raise SkillError('未完整识别八类装备，未更新原资料')
    return list(records.values()),counts

def fetch_equipment():
    try:
        request=Request(SOURCE_URL,headers={'User-Agent':'Dungeon2Simulator/1.0 (equipment reference fetch)','Accept':'text/html'})
        with urlopen(request,timeout=40) as response:
            raw=response.read(5*1024*1024+1)
            if len(raw)>5*1024*1024:raise SkillError('来源页面超过5MB')
            html=raw.decode(response.headers.get_content_charset() or 'utf-8')
        return parse_equipment(html)
    except SkillError:raise
    except (OSError,UnicodeError) as error:raise SkillError('BWIKI抓取失败，请稍后重试；原资料未覆盖',502) from error
